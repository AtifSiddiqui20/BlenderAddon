bl_info = {
    "name": "GP Face Tools",
    "author": "Attaboy!",
    "version": (0, 0, 2),
    "blender": (5, 0, 0),
    "category": "Grease Pencil",
    "location": "View 3D > Tool Shelf > GP Face tool",
    "description": "Create and edit 2d faces with Grease Pencil",
}

# Current work flow:
# 1. Start Rig
# 2. Draw Features
# 3. Build Rig
# 4. Finalize
# 5. Append
# 6. Shrinkwrap

# Create Tab (Currently only tab): No tracking of the rig, just create it.
# Edit Tab: Will find and identify which rigs the user wants to edit based on custom props - stateful UI 
# Misc Tab: No clue right now

# Current missing features for mouths: 
# Naming stuff needs work - check for special characters -DONE -Make sure all names are changed during the end so more face rigs can be made -DONE
# Rig ID - custom props added, need to be used more effeectively
# Cleanup UI, bone sizes/placements and logic to make sure its airtight
# Edit button? - To be added later
# # Use Lights Button
# Append to rig? - Working on it

# Current Issues for Eyes
 #Not yet implemented

# show hidden bones button? - Maybe located in edit mode?
 
# Set Interpolation Mode for keyframes to constant for mouth puck


#General Notes:
#appending to rigs, making the interface use drivers for x and y movement, allowing it to 
# snap to shapes rather than freely move about (only for mouth and eye shapes)

# Lattice creation with bone hooks for every part
# Add Delete Rig button for my collection
# add custom props to make sure only face rigs are edited/created
# go into edit mode for the entire rig - needs some way to idetify which part of the rig is being worked
# on - likely use IDs for each
# Mirror modifier/ button for eyes? Needs to keep origin in mind!

# Adding items during creation to local view?
# Add a button to show control board by itself?

#Tips/things to remember: 
# Always use transform space
# It is the Z location, not Y locaiton.
# apply scaling and rotation to custom bone shape meshes


#missing features:
# Eyes
# Noses
# Eyebrows
# Eyebrow Sliders/controls 
# Widgets 




from asyncio import sleep
import asyncio
from email.mime import text

import bpy
import bmesh
import os
import math
import re
import uuid
from mathutils import Vector
from bpy import context
from bpy.types import (Operator, Menu, Panel, UIList, PropertyGroup)
from bpy.props import (StringProperty, BoolProperty, IntProperty, FloatProperty, EnumProperty, PointerProperty)


#Helper functions

# Set Customs properties for rigs created by this Add-on
def tag_rig_object(object, id, role):
    if object is None: 
        return
    if object.type == 'ARMATURE':
        object["is_Atta_gp_face_rig"] = True
        object["rig_name"] = object.name
    object["rig_version"] = (0, 0, 1)  # Example versioning, can be updated as needed
      
    object["rig_id"] = id  # Store the unique ID for the rig
    object["rig_role"] = role  # Store the role of the rig

def generate_unique_id(prefix="AttaGPFR"):
    no = str(uuid.uuid4())[:8]  # Shorten the UUID for readability
    return f"{prefix}_{no}"

def get_rig_objects(rig_id):
    """Get all objects belonging to a specific rig"""
    return {
        obj["rig_role"]: obj
        for obj in bpy.data.objects
        if obj.get("rig_id") == rig_id
    }

def get_rig_object_by_role(rig_id, role):
    """Get a specific object by its role"""
    for obj in bpy.data.objects:
        if obj.get("rig_id") == rig_id and obj.get("rig_role") == role:
            return obj
    return None

def find_all_face_rigs():
    """Find all face rig armatures in the scene"""
    return [
        obj for obj in bpy.data.objects
        if obj.get("gp_face_rig") and obj.get("rig_role") == "armature"
    ]
    
def get_rig_id(rig_object):
    """Get the rig ID from a rig object"""
    if rig_object and rig_object.get("rig_id"):
        return rig_object["rig_id"]
    return None

#Find the rig using custom properties rather than name to avoid issues with multiple rigs
def find_rig(context):
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE' and obj.get("is_Atta_gp_face_rig"):
            return obj
    return None

def get_face_rig_from_selection(context):
    obj = context.active_object
    if not obj:
        return None
    if obj.type == 'ARMATURE' and obj.get("is_Atta_gp_face_rig"):
        return obj
    return None

def get_bone_distance(armature, bone1_name, bone2_name):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    armature_eval = armature.evaluated_get(depsgraph)
    
    bone1 = armature_eval.pose.bones[bone1_name]
    bone2 = armature_eval.pose.bones[bone2_name]
    
    world_pos1 = armature.matrix_world @ bone1.matrix @ Vector((0, 0, 0))
    world_pos2 = armature.matrix_world @ bone2.matrix @ Vector((0, 0, 0))
    
    distance = (world_pos1 - world_pos2).length
    return distance

def update_onion_skinning(self, context):
    # Pass a lambda so the timer gets a no-argument callable
    bpy.app.timers.register(do_onion_update, first_interval=0.1)

def do_onion_update():
    
    context = bpy.context
    settings = context.scene.grease_pencil_face_rig_settings
    collection = bpy.data.collections.get("Mouth Rig Control Board Objects")
    
    if not collection:
        return None
    
    gp_duplicates = [
        obj for obj in collection.objects 
        if obj and obj.type == 'GREASEPENCIL'
    ]

    # Always hide and reset everything
    for obj in gp_duplicates:
        obj.hide_set(True)
        obj.hide_viewport = True
        for layer in obj.data.layers:
            layer.opacity = 1.0

    if not settings.use_onion_skinning or not gp_duplicates:
        return None

    # Show the selected onion skin
    idx = max(0, min(settings.onion_preview_index, len(gp_duplicates) - 1))
    onion = gp_duplicates[idx]
    onion.hide_set(False)
    onion.hide_viewport = False
    apply_onion_opacity(onion, settings.onion_opacity)
    
    return None  # unregisters timer after one run


def apply_onion_opacity(ghost_obj, opacity):
    if not ghost_obj or ghost_obj.type != 'GREASEPENCIL':
        return
    for layer in ghost_obj.data.layers:
        layer.opacity = opacity


def get_onion_max(self):
    collection = bpy.data.collections.get("Mouth Rig Control Board Objects")
    if not collection:
        return 0
    count = len([
        obj for obj in collection.objects
        if obj and obj.type == 'GREASEPENCIL'
        
    ])
    return max(0, count -1 )

def get_onion_index(self):
    # Clamp stored value to valid range
    max_val = get_onion_max(self)
    return max(0, min(self.get("onion_preview_index", 0), max_val))

# update callback on the index property also just calls the same function
def update_onion_index(self, context):
    
    
    bpy.app.timers.register(do_onion_update, first_interval=0.01)
    
def set_onion_index(self, value):
    max_val = get_onion_max(self)
    self["onion_preview_index"] = max(0, min(value, max_val))
    # Trigger the update manually since get/set bypasses update callback
    bpy.app.timers.register(do_onion_update, first_interval=0.01)


def update_onion_opacity(self, context):
    bpy.app.timers.register(do_onion_update, first_interval=0.01)





# Main property group for the add-on, storing all relevant settings for the face rig creation and editing process.
class GreasePencilFaceRigSettings(bpy.types.PropertyGroup):
    mouth_shape_name: str
    mouth_shape_name: bpy.props.StringProperty(
        name="Mouth Shape Name",
        description="Enter a name for the mouth shape",
        default="",
        maxlen=25,
    )
    rig_name: str
    rig_name: bpy.props.StringProperty(
        name="Rig Name",
        description="Enter a name for the rig (used for organization, not object naming)",
        default="Character",
        maxlen=25,
    )
    use_onion_skinning: bpy.props.BoolProperty(
        name="Use Onion Skinning",
        description="Enable onion skinning for the face rig",
        default=False,
        update = update_onion_skinning
    )
    onion_opacity: bpy.props.FloatProperty(
        name="Onion Skinning Opacity",
        description="Opacity for onion skinning",
        default=0.3,
        min=0.0,
        max=1.0,
        update=update_onion_skinning
    )
    onion_preview_index: bpy.props.IntProperty(
        name="Preview Shape",
        default=0,
        min=0,
        get=get_onion_index,
        set=set_onion_index,
        update=update_onion_index
    )
    Eye_shape_name: str
    Eye_shape_name: bpy.props.StringProperty(
        name="Eye Shape Name",
        description="Enter a name for the eye shape",
        default="",
        maxlen=25,
    )
#     rig_mode_shape: bpy.props.EnumProperty(
#         name = "Rig Mode",
#         description = "Currrent Grease Pencil Face Shape mode",
#         items= [('NONE', "None", ""),
#             ('MOUTHS', "Mouth", ""),
#             ('EYES', "Eyes", ""),
#             ('NOSE', "Nose", "")
#         ],
#         default='NONE'
#         # context.scene.face_rig_settings.rig_mode = 'MOUTH' - how to set
# #        settings = context.scene.face_rig_settings
# #        if settings.rig_mode == 'MOUTH':
# #            layout.label(text="Mouth Tools")
# #          how to check it
#     )
    
class ShrinkwrapSettings(bpy.types.PropertyGroup):
    target_object: bpy.props.PointerProperty(
        name="Shrinkwrap Target",
        description="Object to shrinkwrap to",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
    )
    target_lattice: bpy.props.PointerProperty(
        name="Shrinkwrap Lattice",
        description="Lattice to use for deformation (optional)",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'LATTICE'
    )
    wrap_method: bpy.props.EnumProperty(
     name = "Shrinkwrap Method",
     items = [('NEAREST_SURFACEPOINT', "Nearest Surface Point", ""),
              ('PROJECT', "Project", ""),
              ('NEAREST_VERTEX', "Nearest Vertex", "")],
        default='NEAREST_SURFACEPOINT'   
    )
    wrap_mode: bpy.props.EnumProperty(
        name = "Shrinkwrap Mode",
        items = [('ON_SURFACE', "On Surface", ""),
                 ('INSIDE', "Inside", ""),
                 ('OUTSIDE', "Outside", ""),
                 ('OUTSIDE_SURFACE', "Outside Surface", ""),
                 ('ABOVE_SURFACE', "Above Surface", "")],
        
        default='ABOVE_SURFACE'
    )
    offset: bpy.props.FloatProperty(   
        name="Shrinkwrap Offset",
        description="Distance to keep from the target surface",
        default=0.01,
        min=0.0,
        max=1.0
    )
    use_negative_direction: bpy.props.BoolProperty(
        name="Use Negative Direction",  
        default=False
    )
    
    use_positive_direction: bpy.props.BoolProperty(
        name="Use Positive Direction",
        default=False
    )
    
class TargetRigSettings(bpy.types.PropertyGroup):
    target_rig: bpy.props.PointerProperty(
        name="Target Rig",
        description="The existing rig to append to",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE'
    )
    head_bone_name: bpy.props.StringProperty(
        name="Head Bone Name",
        description="Name of the head bone in the target rig",
        default="Head"
    )
    face_rig: bpy.props.PointerProperty(
        name="Face Rig",
        description="The face rig to append to",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE'
    )

# Operator to center view on the world origin and get correctly set up 
class SetUp(bpy.types.Operator):
    "Sets up temp collections, bones, and grease pencil objects for the face rig creation process"
    bl_idname = "view3d.setup"
    bl_label = "Create Grease Pencil Faces"
    bl_options = {'REGISTER', 'UNDO'}
    
    #@classmethod
    #def poll(cls, context):
        #return context.Scene.gp_active_tab == 'CREATE'
    
    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.view3d.view_axis(type='FRONT')
        # Collection handling
        collection_name = "Temp Drawing Collection"
        if collection_name not in bpy.data.collections:
            collection = bpy.data.collections.new(collection_name)
            context.scene.collection.children.link(collection)
        else:
            collection = bpy.data.collections[collection_name]
            
        # Material setup
        if "Default Face Material" in bpy.data.materials.keys():
            gp_mat = bpy.data.materials["Default Face Material"]
            bpy.data.materials.create_gpencil_data(gp_mat)
            
            
        else:
            gp_mat = bpy.data.materials.new("Default Face Material")
            bpy.data.materials.create_gpencil_data(gp_mat)
            
              
        gp_mat.use_nodes = False 
        gp_mat.grease_pencil.color = (0, 0, 0, 1)    
        
            
        context.scene.has_setup_been_run = True
        
        return {'FINISHED'}
    
     
############################### EYES ########################

# Notes for eyes:
##General Notes:
#Number of eyes -  
#Also will need to arrange eyes in a way based on number of eyes
# Mirroring - ideally would like to just draw one eye and have it mirror to the other - will ikley need scaling manually moving into position for the second eye, but can use a mirror modifier to mirror the strokes. Will need to make sure the origin is in the right place for this.
##Eye Shapes:
#Eye shapes will operate in a staged process, so eye1 must be completed before eye2, etc. Will need to add some logic to check for this. 
# will use the same methodology as mouth shapes, but will we need to have each eye use different drivers? will allow for multi shape eye rigs, 
# but will require more set up. How would this work for a large amount of eyes?
# need to follow structure of eye workflow

#Layer set up-

#Effects
#pupil
#Iris
#Eye lids/base shape - think of the eye "outline"
#Sclera

class EyeItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(default="Eye")
    gp_object: bpy.props.PointerProperty(type=bpy.types.Object)
    mirror: bpy.props.BoolProperty(default=True)
    active_layer: bpy.props.StringProperty(default="sclera")
    
class FinishEyeShape(bpy.types.Operator):
    """Duplicate Eye drawings, scale, move them to correct locations on control board"""
    bl_idname = "grease_pencil.finish_eye_shapes"
    bl_label = "Finish Eye Shape"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.scene.gp_face_mode == 'EYES'
    
    
    def execute(self, context):
        return
    


class ViewCenterOriginEyes(bpy.types.Operator):
    "Begin drawing and creation process for eye objects"
    bl_idname = "view3d.center_origin_eyes"
    bl_label = "Create Eye shapes"
    bl_options = {'REGISTER', 'UNDO'}
    
    #poll method to check if eye mode have been entered - for edit mode?
    
    def execute(self, context):
        
        context.scene.gp_face_mode = 'EYES'
        bpy.ops.view3d.view_axis(type='FRONT')
        collection_name = "Temp Drawing Collection"
        if collection_name not in bpy.data.collections:
            collection = bpy.data.collections.new(collection_name)
            context.scene.collection.children.link(collection)
        else:
            collection = bpy.data.collections[collection_name]
            
            # Plane creation and setup -- offset from center 
        plane_name = "Target Eye Drawing Plane"
        plane = bpy.data.objects.get(plane_name)
        if not plane:
            #is this the right location for the eye drawing plane? Maybe it should be moved up a bit?
            bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=False, location=(.1, 0, 0.2), rotation=(1.5708, 0, 0)) 
            plane = context.active_object
            plane.name = plane_name
            plane.scale = (.08, .08, .08)
            collection.objects.link(plane)  # Ensure it's in the right collection
            context.collection.objects.unlink(plane)  # Unlink from default collection
            #Need logic for mirroring the GP via modifiers rather than just drawing both sides
            #Need logic for multiple eyes as well, currently only set up for one pair

        self.delete_plane_faces_eyes(plane)
        plane.display_type = 'WIRE'
        self.zoom_to_object_eyes(plane)
        self.make_plane_unselectable_eyes(plane)
        
        gp_name = "GP Temp Eye Object"
        if gp_name not in bpy.data.objects:
            gp_data = bpy.data.grease_pencils.new(gp_name)
            gp_obj = bpy.data.objects.new(gp_name, gp_data)
            collection.objects.link(gp_obj)
        else:
            gp_obj = bpy.data.objects[gp_name]
            gp_data = gp_obj.data
        
        gp_obj.location = (.1, 0, .2)
        context.view_layer.objects.active = gp_obj
        gp_obj.select_set(True)
        bpy.ops.object.mode_set(mode = 'EDIT')
        # How to access tool menu--
        bpy.context.scene.tool_settings.gpencil_sculpt.use_scale_thickness = True
        bpy.ops.object.mode_set(mode='PAINT_GREASE_PENCIL')
        new_layer = gp_obj.data.layers.new(name="New GP Layer", set_active=True)
        new_layer.name = "New GP Layer"  # Optional: set a name for the layer
        new_layer.frames.new(frame_number=1)  # Ensure there's a frame to draw on

        # Material setup
        if "Default Face Material" in bpy.data.materials.keys():
            gp_mat = bpy.data.materials["Default Face Material"]
            bpy.data.materials.create_gpencil_data(gp_mat)
            
            
        else:
            gp_mat = bpy.data.materials.new("Default Face Material")
            bpy.data.materials.create_gpencil_data(gp_mat)
            
              
        gp_mat.use_nodes = False 
        gp_data.materials.append(gp_mat)
        gp_mat.grease_pencil.color = (0, 0, 0, 1)    
        
        
        return {'FINISHED'}
    

    
    def delete_plane_faces_eyes(self, obj):
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.delete(type='ONLY_FACE')
        bpy.ops.object.mode_set(mode='OBJECT')

    def zoom_to_object_eyes(self, obj):
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        with bpy.context.temp_override(area=area, region=region, space_data=area.spaces.active):
                            bpy.ops.view3d.view_axis(type = 'FRONT')
                            bpy.ops.view3d.view_selected(use_all_regions=False)
                        
                            break
        obj.hide_select = True

    def make_plane_unselectable_eyes(self, obj):
        # Get the object by name and check if it is not None
        if bpy.context.view_layer.objects.get(obj.name) is not None:
            obj.hide_select = True
            obj.hide_render = True

    def create_default_gp_material(self, gp_obj):
        # Create a new material
        
        if not gp_obj.data.materials:
            mat = bpy.data.materials.new(name="GP Default Material")
            bpy.data.materials.create_gpencil_data(mat)
            mat.grease_pencil.color = (0.4, 0.2, 0.8, 1.0)
            gp_obj.data.materials.append(mat)
        bpy.ops.grease_pencil.paintmode_toggle()
        return gp_obj.data.materials[0]
    
    
class MY_OT_set_eye_layer(bpy.types.Operator):
    bl_idname = "my.set_eye_layer"
    bl_label = "Set Eye Layer"
    
    layer_name: bpy.props.StringProperty()

    def execute(self, context):
        gp = context.scene.active_eye_object  # your tracked GP object
        if not gp or gp.type != 'GPENCIL':
            return {'CANCELLED'}

        for layer in gp.data.layers:
            layer.lock = (layer.info != self.layer_name)  # lock all but target
            layer.hide = False  # keep all visible

        # Set active layer
        gp.data.layers.active = gp.data.layers.get(self.layer_name)
        return {'FINISHED'}
    
    
class finishEyeShape(bpy.types.Operator):
    """Duplicate Eye drawings, scale, move them to correct locations on control board"""
    bl_idname = "grease_pencil.finish_eye_shapes"
    bl_label = "Finish Eye Shape"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.scene.gp_face_mode == 'EYES'
    
    
    def is_layer_empty(self, layer):
        """Check if a Grease Pencil layer is empty"""
        for GPencilframe in layer.frames:
            if GPencilframe.items:
                return False
        return True
    
    def execute(self, context):
        eye_name = bpy.context.scene.grease_pencil_face_rig_settings.Eye_shape_name
        if not eye_name:
            self.report({'WARNING'}, "You should enter a name for the eye shape")
            return {'CANCELLED'}
        gp_obj = context.active_object
        if gp_obj and gp_obj.type == 'GREASEPENCIL':
            
            all_empty = True
            for layer in gp_obj.data.layers:
                if not layer.hide and not self.is_layer_empty(layer):
                    all_empty = False
                    break

            if all_empty:
                self.report({'WARNING'}, "No shapes drawn in visible layers")
                return {'CANCELLED'}
            for layer in gp_obj.data.layers:
                if not layer.hide:
                    layer.name = eye_name
                    
            
        return {'FINISHED'}
            
            
            
############################# NOSE ##########################

class viewCenterOriginNose(bpy.types.Operator):
    "Begin drawing and creation process for nose objects"
    bl_idname = "view3d.center_origin_nose"
    bl_label = "Create Nose shapes"
    bl_options = {'REGISTER', 'UNDO'}
    
    #poll method to check if nose mode have been entered
    
    def execute(self, context):
        bpy.ops.view3d.view_axis(type='FRONT')
        collection_name = "Temp Drawing Collection"
        if collection_name not in bpy.data.collections:
            collection = bpy.data.collections.new(collection_name)
            context.scene.collection.children.link(collection)
        else:
            collection = bpy.data.collections[collection_name]
            
        return {'FINISHED'}
    
    
############################# MOUTHS ########################




class ViewCenterOriginMouths(bpy.types.Operator):
    "Center the view on the world origin, add a plane, create a Grease Pencil object with a correctly configured material, and enter draw mode"""
    bl_idname = "view3d.center_origin"
    bl_label = "Create Grease Pencil Mouth Object"
    bl_options = {'REGISTER', 'UNDO'}
    
    
            
        
    def execute(self, context):
        
        context.scene.gp_face_mode = 'MOUTHS'
        bpy.ops.view3d.view_axis(type='FRONT')

        # Collection handling -- Move these to set up
        collection_name = "Temp Drawing Collection"
        if collection_name not in bpy.data.collections:
            collection = bpy.data.collections.new(collection_name)
            context.scene.collection.children.link(collection)
        else:
            collection = bpy.data.collections[collection_name]
            
        

        # Plane creation and setup
        plane_name = "Target Face Drawing Plane"
        plane = bpy.data.objects.get(plane_name)
        if not plane:
            bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=False, location=(0, 0, 0), rotation=(1.5708, 0, 0))
            plane = context.active_object
            plane.name = plane_name
            plane.scale = (.2, .1, .1)
            collection.objects.link(plane)  # Ensure it's in the right collection
            context.collection.objects.unlink(plane)  # Unlink from default collection

        self.delete_plane_faces(plane)
        plane.display_type = 'WIRE'
        self.zoom_to_object(plane)
        self.make_plane_unselectable(plane)

        # Grease Pencil object and material setup - 
        gp_name = "GP Temp Face Object"
        if gp_name not in bpy.data.objects:
            gp_data = bpy.data.grease_pencils.new(gp_name)
            gp_obj = bpy.data.objects.new(gp_name, gp_data)
            collection.objects.link(gp_obj)
        else:
            gp_obj = bpy.data.objects[gp_name]
            gp_data = gp_obj.data

        gp_obj.location = (0, 0, 0)
        context.view_layer.objects.active = gp_obj
        gp_obj.select_set(True)
        bpy.ops.object.mode_set(mode = 'EDIT')
        # How to access tool menu--
        bpy.context.scene.tool_settings.gpencil_sculpt.use_scale_thickness = True
        bpy.ops.object.mode_set(mode='PAINT_GREASE_PENCIL')
        new_layer = gp_obj.data.layers.new(name="New GP Layer", set_active=True)
        new_layer.name = "New GP Layer"  # Optional: set a name for the layer
        new_layer.frames.new(frame_number=1)  # Ensure there's a frame to draw on

        # Material setup
        if "Default Face Material" in bpy.data.materials.keys():
            gp_mat = bpy.data.materials["Default Face Material"]
            bpy.data.materials.create_gpencil_data(gp_mat)
            
            
        else:
            gp_mat = bpy.data.materials.new("Default Face Material")
            bpy.data.materials.create_gpencil_data(gp_mat)
            
              
        gp_mat.use_nodes = False 
        gp_data.materials.append(gp_mat)
        gp_mat.grease_pencil.color = (0, 0, 0, 1)    
        
        

        return {'FINISHED'}

    def delete_plane_faces(self, obj):
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.delete(type='ONLY_FACE')
        bpy.ops.object.mode_set(mode='OBJECT')

    def zoom_to_object(self, obj):
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        with bpy.context.temp_override(area=area, region=region, space_data=area.spaces.active):
                            bpy.ops.view3d.view_axis(type = 'FRONT')
                            bpy.ops.view3d.view_selected(use_all_regions=False)
                        
                            break
        obj.hide_select = True

    def make_plane_unselectable(self, obj):
        # Get the object by name and check if it is not None
        if bpy.context.view_layer.objects.get(obj.name) is not None:
            obj.hide_select = True
            obj.hide_render = True

    def create_default_gp_material(self, gp_obj):
        # Create a new material
        
        if not gp_obj.data.materials:
            mat = bpy.data.materials.new(name="GP Default Material")
            bpy.data.materials.create_gpencil_data(mat)
            mat.grease_pencil.color = (0.4, 0.2, 0.8, 1.0)
            gp_obj.data.materials.append(mat)
        bpy.ops.grease_pencil.paintmode_toggle()
        return gp_obj.data.materials[0]




class FinishMouthShape(bpy.types.Operator):
    """Duplicate the GP object, scale it, move it, and prepare the original for new drawing"""
    bl_idname = "grease_pencil.finish_mouth_shape"
    bl_label = "Finish Mouth Shape"
    bl_options = {'REGISTER', 'UNDO'}
    
    

    def is_layer_empty(self, layer):
        """Check if a Grease Pencil layer is empty"""
        for GPencilframe in layer.frames:
            if GPencilframe.items:
                return False
        return True
    
        

    def execute(self, context):
        
        settings = context.scene.grease_pencil_face_rig_settings
        # Get the name for the mouth shape from the property group
        mouth_name = settings.mouth_shape_name
        # Check if the mouth shape name is provided
        if not mouth_name:
            self.report({'WARNING'}, "You should enter a name for the mouth shape")
            return {'CANCELLED'}
        # Get the active object
        gp_obj = context.active_object
        if not gp_obj or gp_obj.type != 'GREASEPENCIL':
            self.report({'ERROR'}, "Active object is not a Grease Pencil object.")
            return {'CANCELLED'}
        
        # if settings.use_framemode:
        #     return self.finish_mouth_shape_frame_mode(context, gp_obj, mouth_name)
        # else:
        #     return self.finish_mouth_shape_layer_mode(context, gp_obj, mouth_name)
    
        if gp_obj and gp_obj.type == 'GREASEPENCIL':
            # Check if all visible layers are empty
            all_empty = True
            for layer in gp_obj.data.layers:
                if not layer.hide and not self.is_layer_empty(layer):
                    all_empty = False
                    break

            if all_empty:
                self.report({'WARNING'}, "No shapes drawn in visible layers")
                return {'CANCELLED'}
            for layer in gp_obj.data.layers:
                if not layer.hide:
                    layer.name = mouth_name
            # Duplicate the Grease Pencil object
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            gp_obj.select_set(True)
            bpy.ops.object.duplicate()
            gp_duplicate = context.active_object
            # Set gp_duplicate name to the provided mouth shape name
            gp_duplicate.name = mouth_name
            for layer in gp_duplicate.data.layers:
                if layer.hide:
                    #Deletes all layers that are hidden
                    gp_duplicate.data.layers.remove(layer)
            
        #assign each dup layer to vertex group for eventual bone parenting 
    
            if gp_duplicate and gp_duplicate.type == 'GREASEPENCIL':
            # Create or get the vertex group
                vgroup_name = mouth_name + " Shape Bone"
                if vgroup_name not in gp_duplicate.vertex_groups:
                    gp_duplicate.vertex_groups.new(name=vgroup_name)
                # Enter edit mode
                bpy.ops.object.mode_set(mode='EDIT')
#                # Reveal all existing layers in the original GP object
#                for layer in gp_duplicate.data.layers:
#                    layer.hide = False
                # Select all strokes
                
                bpy.ops.grease_pencil.select_all(action='SELECT')
                # Assign selected vertices to the vertex group
                for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                
                                with bpy.context.temp_override(
                                        area=area,
                                        region=region,
                                        edit_object=bpy.context.edit_object
                                ):
                                    bpy.ops.object.vertex_group_assign()
                                break
                bpy.ops.object.mode_set(mode='OBJECT')
                self.report({'INFO'}, "Vertices added to mouth controller vertex group.")

            # Scale the duplicate
            # Gonna need to do this later
            #gp_duplicate.scale *= 2.5
            #bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

            # Create or get the "Mouth Rig Control Board Objects" collection within "Temp Drawing Collection"
            parent_collection_name = "Temp Drawing Collection"
            new_collection_name = "Mouth Rig Control Board Objects"
            

            parent_collection = bpy.data.collections.get(parent_collection_name)
            if not parent_collection:
                parent_collection = bpy.data.collections.new(parent_collection_name)
                context.scene.collection.children.link(parent_collection)

            new_collection = bpy.data.collections.get(new_collection_name)
            if not new_collection:
                new_collection = bpy.data.collections.new(new_collection_name)
                parent_collection.children.link(new_collection)
            else:
                if new_collection.name not in parent_collection.children:
                    parent_collection.children.link(new_collection)

            
            
            # Create a text object for the mouth shape name
            bpy.ops.object.text_add(enter_editmode=False, location=(gp_duplicate.location.x, gp_duplicate.location.y, gp_duplicate.location.z - 0.2))
            text_obj = context.active_object
            text_obj.data.body = mouth_name
            
            text_obj.rotation_euler = (1.5708, 0, 0) 
            text_obj.name = mouth_name + "Text" 
            # Set text alignment to center
            text_obj.data.align_x = 'CENTER'
            text_obj.data.align_y = 'CENTER'
            
            # Calculate the scale based on the length of the text
            base_scale = 0.04
            text_length = len(text_obj.data.body)

            # Adjust the scale inversely proportional to the length of the text
            scale_factor = base_scale / (text_length * 0.2)
            if text_length > 6:
                text_obj.scale = (scale_factor, scale_factor, scale_factor)
            else:
                text_obj.scale = (.06, .06, .06)
            
            # Link the text object & Duplicate to the new collection -- 
            if gp_duplicate.name not in new_collection.objects:
                new_collection.objects.link(gp_duplicate)
            if text_obj.name not in new_collection.objects:
                new_collection.objects.link(text_obj)
            
            for col in gp_duplicate.users_collection:
                if col != new_collection:
                    col.objects.unlink(gp_duplicate)
            for col in text_obj.users_collection:
                if col != new_collection:
                    col.objects.unlink(text_obj)
                    
                    
            # Parent the text object to the duplicated GP object
            text_obj.select_set(True)
            gp_duplicate.select_set(True)
            context.view_layer.objects.active = gp_duplicate
            bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
            gp_duplicate.hide_viewport = True
            text_obj.hide_viewport =True
            
            
            # Get the count of finished mouth shapes
            # Increment the count
            count = context.scene.finish_mouth_count
            context.scene.finish_mouth_count += 1

            # Return to the original Grease Pencil object
            bpy.ops.object.select_all(action='DESELECT')
            context.view_layer.objects.active = gp_obj
            gp_obj.select_set(True)

            # Hide all existing layers in the original GP object
            for layer in gp_obj.data.layers:
                layer.hide = True

            # Create a new layer in the original GP object
            new_layer = gp_obj.data.layers.new(name="New Mouth Layer", set_active=True)
            new_layer.name = "New Mouth Layer"  # Optional: set a name for the layer
            new_layer.frames.new(frame_number=1)  # Ensure there's a frame to draw on

            # Enter draw mode on the original GP object
            bpy.ops.object.mode_set(mode='PAINT_GREASE_PENCIL')

            # Clear the mouth_shape_name property
            context.scene.grease_pencil_face_rig_settings.mouth_shape_name = ""

            self.report({'INFO'}, "Mouth shape finished. Ready for new drawing.")
            return {'FINISHED'}
        self.report({'ERROR'}, "Active object is not a Grease Pencil object.")
        return {'CANCELLED'}
    
    
    # def finish_mouth_shape_frame_mode(self, context, gp_obj, mouth_name):
    #     settings = context.scene.grease_pencil_face_rig_settings
    #     layer = gp_obj.data.layers.active
    #     if not layer:
    #         self.report({'ERROR'}, "No active layer found.")
    #         return {'CANCELLED'}
    #     current_frame = context.scene.frame_current
    #     if not self.check_if_auto_keying_is_on():
    #         bpy.context.scene.tool_settings.use_keyframe_insert_auto = True
    #         self.report({'INFO'}, "Auto keyframing has been enabled.")
    #     item = context.scene.mouth_frames.add()
    #     item.frame_number = current_frame
    #     item.mouth_name = mouth_name
    #     self.report({'INFO'}, f"Mouth shape '{mouth_name}' recorded at frame {current_frame}.")
    #     next_frame = current_frame + 1
    #     context.scene.frame_current = next_frame
        
    #     if not layer.frames.get(next_frame):
    #         layer.frames.new(frame_number=next_frame)
    #         settings.mouth_shape_name = ""
    #         context.scene.finish_mouth_count += 1
    #         self.report({'INFO'}, f"Moved to frame {next_frame} for next mouth shape.")
    #         return {'FINISHED'}
    
    
    def check_if_auto_keying_is_on(self):
        if not bpy.context.scene.tool_settings.use_keyframe_insert_auto:
            self.report({'WARNING'}, "Auto keyframing is not enabled. Please enable it to use frame mode.")
            return False
        return True



class GPDoneDrawingMouth(bpy.types.Operator):
    """Exit draw mode and arrange duplicated GP objects"""
    bl_idname = "grease_pencil.done_drawing"
    bl_label = "Done"
    bl_options = {'REGISTER', 'UNDO'}
    
    def remove_object_by_name(self, name):
        if name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
        

    def execute(self, context):
        
        
        settings = context.scene.grease_pencil_face_rig_settings
        
        
        #if context.scene.mouth_frames != None and len(context.scene.mouth_frames) > 0:
            
        # Ensure there are no name conflicts
        self.remove_object_by_name("Mouth Shape Control Selector")
        context.active_object.select_set(True)
        gp_obj = context.active_object
        
        if gp_obj and gp_obj.type == 'GREASEPENCIL':
            # Create or get the vertex group
            vgroup_name = "GP Mouth Bone"
            if vgroup_name not in gp_obj.vertex_groups:
                gp_obj.vertex_groups.new(name=vgroup_name)

            # if settings.use_framemode:
            #     return {'FINISHED'}
            # Enter edit mode
            bpy.ops.object.mode_set(mode='EDIT')

            # Reveal all existing layers in the original GP object
            for layer in gp_obj.data.layers:
                layer.hide = False
                if (layer.name == "New Mouth Layer"):
                    gp_obj.data.layers.remove(layer)


            # Select all strokes
            bpy.ops.grease_pencil.select_all(action='SELECT')

            # Assign selected vertices to the vertex group
            #Old will need updating
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            with bpy.context.temp_override(
                                    area = area,
                                    region = region,
                                    edit_object = bpy.context.edit_object
                            ):
                                bpy.ops.object.vertex_group_assign()
                            break
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, "Vertices added to mouth controller vertex group.")

        # Arrange the duplicated objects in the "Duplicated GP Objects" collection
        collection_name = "Mouth Rig Control Board Objects"
        collection = bpy.data.collections.get(collection_name)

        board_scale = 0.5
        
        if collection is not None:
            spacing_x = 0.25 
            spacing_z = 0.25 
            items_per_row = 4
            x = 1.05 
            z = .4 

            gp_object_count = 0
            for obj in collection.objects:
                obj.hide_viewport = False
                if obj.type == 'GREASEPENCIL':
                    # make sure the object is visible and selectable
                    
                    obj.hide_viewport = False
                    obj.hide_set(False)
                    for layer in obj.data.layers:
                        layer.opacity = 1.0
                    obj.location.x = x
                    obj.location.z = z
                    gp_object_count += 1
                    x += spacing_x

                    if (gp_object_count % items_per_row == 0):
                        x = 1.05
                        z -= spacing_z
                        obj.scale *= 2.5 * board_scale
                elif obj.type == 'FONT':
                    obj.location.z = obj.location.z + 0.1 

            num_rows = math.ceil(gp_object_count / items_per_row)
            bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=True, location=(2 , 0, 2), rotation=(1.5708, 0, 0))
            plane = context.active_object
            plane.name = "Mouth Shapes Control Plane"

            plane.scale = (2 * board_scale, num_rows * 0.5 * board_scale, num_rows / 1.9 * board_scale)
            # Change origin to the leftmost top vertex
            plane_mesh = plane.data
            bmesh_plane = bmesh.from_edit_mesh(plane_mesh)

            # Ensure lookup table is up-to-date
            bmesh_plane.verts.ensure_lookup_table()

            # Deselect all vertices first
            for v in bmesh_plane.verts:
                v.select = False

            # Select only the top left vertex (index 2 for a rotated plane)
            bmesh_plane.verts[2].select = True

            # Ensure the selection mode is set to vertex
            bpy.ops.mesh.select_mode(type='VERT')

            # Update the BMesh and the mesh in Blender
            bmesh.update_edit_mesh(plane_mesh)

            # Create an override context for the VIEW_3D area and region
            
            for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                # Using temp_override for cleaner context override
                                with bpy.context.temp_override(
                                        area=area,
                                        region=region,
                                        edit_object = plane
                                ):
                                    bpy.ops.view3d.snap_cursor_to_selected()
                                break
                            else:
                                continue
                            break

            # Return to object mode and set the origin to the cursor
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
            bpy.context.scene.cursor.location = (0, 0, 0)  # Reset the cursor location

            plane.location.x = .9 
            plane.location.z = .5
            
             

            # Make the plane unselectable and change its display type to wire
            plane.display_type = 'WIRE'
            # plane.hide_select = True
            plane.hide_render = True
            
             # Apply the scale transformation
            bpy.ops.object.mode_set(mode='OBJECT')  # Ensure we are in object mode
            bpy.context.view_layer.objects.active = plane
            bpy.ops.object.transform_apply(location=False, scale=True, rotation=False)
           

            # Add the plane to the "Mouth Rig Control Board Objects" collection
            collection.objects.link(plane)
            context.collection.objects.unlink(plane)
            
            # Create a puck (mesh circle) and place it on top of the first duplicated object
            first_dup_obj = collection.objects[0] if collection.objects else None
            if first_dup_obj:
                bpy.ops.mesh.primitive_circle_add(fill_type='NGON', vertices=16, radius=0.035, location=(
                first_dup_obj.location.x, first_dup_obj.location.y, first_dup_obj.location.z), rotation=(1.5708, 0, 0))
                puck = context.active_object
                puck.name = "Mouth Shape Control Selector"
                bpy.ops.object.mode_set(mode='OBJECT')
                bpy.context.view_layer.objects.active = puck
                bpy.ops.object.transform_apply(location=False, scale=True, rotation=False)
                # puck.transform_apply(location = False, Scale = True, Rotation = False)
                # puck.hide_render = True
                collection.objects.link(puck)
                context.collection.objects.unlink(puck)

            # Hide everything in the collection from render view
            for obj in collection.objects:
                obj.hide_render = True
                # Parent only GP objects in the collection to the plane 
# Now using Constraints for this
#                if obj != plane: 
#                    if obj.type == 'GREASE_PENCIL': 
#                        obj.select_set(True)
#                        plane.select_set(True)
#                        context.view_layer.objects.active = plane
#                        bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
#                        obj.select_set(False)
            
            #unparent the puck
            puck = bpy.data.objects["Mouth Shape Control Selector"]
            puck.select_set(True)
            context.view_layer.objects.active = puck
            bpy.ops.object.parent_clear(type = 'CLEAR_KEEP_TRANSFORM')
            puck.select_set(False)
            

            # Return to GREASE_PENCIL object
            bpy.ops.object.select_all(action='DESELECT')
            gp_obj.select_set(True)
            context.view_layer.objects.active = gp_obj
            
            #Create lattice for the mouth object
             # Add a lattice
            bpy.ops.object.add(type='LATTICE', enter_editmode=False, align='WORLD', location=(0, 0, 0), scale=(2, .2, 1))

            lattice = context.active_object
            lattice.name = "GPMouthLattice"
            lattice.data.interpolation_type_u = 'KEY_BSPLINE'
            lattice.data.interpolation_type_v = 'KEY_BSPLINE'
            lattice.data.interpolation_type_w = 'KEY_BSPLINE'
            lattice.data.points_u = 6 
            lattice.data.points_v = 2  
            lattice.data.points_w = 6  
            lattice.scale[0] = .2
            lattice.scale[1] = .03
            lattice.scale[2] = .1
            
            

            # Add a lattice modifier to the GP object
            bpy.ops.object.select_all(action='DESELECT')
            gp_obj.select_set(True)
            context.view_layer.objects.active = gp_obj
            mod = bpy.ops.object.modifier_add(type='GREASE_PENCIL_LATTICE')
            bpy.context.object.modifiers["Lattice"].object = bpy.data.objects["GPMouthLattice"]
            
            context.collection.objects.unlink(lattice)
            collection.objects.link(lattice)
            # Put GP back to active
            bpy.ops.object.select_all(action='DESELECT')
            gp_obj.select_set(True)
            

            self.report({'INFO'},
                        f"Arranged {len(collection.objects)} objects in {(len(collection.objects) + items_per_row - 1) // items_per_row} rows.")
        else:
            self.report({'ERROR'}, f"Collection '{collection_name}' not found.")

        return {'FINISHED'}
    
    
    
############################### Face Creation Operators ########################

class GPAddNewLayer(bpy.types.Operator):
    """Add a new layer to the active Grease Pencil object"""
    bl_idname = "grease_pencil.add_new_layer"
    bl_label = "New Layer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        gp_obj = context.active_object
        if gp_obj and gp_obj.type == 'GREASEPENCIL':
            new_layer = gp_obj.data.layers.new(name="New GP Layer", set_active=True)
            new_layer.name = "New GP Layer"  # Optional: set a name for the layer
            new_layer.frames.new(frame_number=1)  # Ensure there's a frame to draw on
            face_layer_count = context.scene.face_layers
            face_layer_count += 1
            self.report({'INFO'}, "New layer added and activated for drawing.")
            return {'FINISHED'}
        self.report({'ERROR'}, "Active object is not a Grease Pencil object.")
        return {'CANCELLED'}



#Mouth lattice helper functions:
def build_mouth_hook_map():
    
    def get_range(u_range, v_range, w_range):
        return [
            get_lattice_index(u, v, w)
            for w in w_range
            for v in v_range
            for u in u_range
        ]
    
    hook_map = {
        # Corners
        # "Mouth_Corner_R": get_range(
        #     range(0, 3),   # left half U
        #     range(0, 2),   # all V
        #     range(3, 6)    
        # ),
        # "Mouth_Corner_L": get_range(
        #     range(3, 6),   # right half U
        #     range(0, 2),
        #     range(3, 6)    # top half W
        # ),

        # Upper lip (W 3-5, the TOP half)
        "Mouth_Top_R": get_range(
            range(0, 2),
            range(0, 2),
            range(3, 6)    
        ),
        "Mouth_Top_C": get_range(
            range(2, 4),
            range(0, 2),
            range(3, 6)
        ),
        "Mouth_Top_L": get_range(
            range(4, 6),
            range(0, 2),
            range(3, 6)
        ),

        # Lower lip (W 0-2, the BOTTOM half)
        "Mouth_Bot_R": get_range(
            range(0, 2),
            range(0, 2),
            range(0, 3)    
        ),
        "Mouth_Bot_C": get_range(
            range(2, 4),
            range(0, 2),
            range(0, 3)
        ),
        "Mouth_Bot_L": get_range(
            range(4, 6),
            range(0, 2),
            range(0, 3)
        ),

        # Depth — back V layer
        # "Mouth_Depth": get_range(
        #     range(0, 6),
        #     range(1, 2),
        #     range(0, 6)
        # ),
    }
    return hook_map
    
def get_lattice_index(u, v, w, res_u=6, res_v=2, res_w=6):
    return u + (v * res_u) + (w * res_u * res_v)


def create_bone_shape(name, shape_type='CIRCLE', scale=(0.1, 0.1, .1), rotation=(0, 0, 0), delete_faces=True, label=""):
    #Bone Head will be at the CENTER of the mesh - so the center of shapes should be at bottom of the mesh or the bone head should be offset.
    # Create a new mesh object to use as the bone shape
    if shape_type == 'CIRCLE':
        bpy.ops.mesh.primitive_circle_add(vertices=32, radius=0.5)
    elif shape_type == 'SQUARE':
        bpy.ops.mesh.primitive_plane_add(size=1)
    elif shape_type == 'ARROW':
        bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.3, depth=0.6)
        bpy.context.active_object.rotation_euler = (0, 0, 0)
        bpy.ops.object.transform_apply(rotation=True)
    elif shape_type == 'TEXT':
        bpy.ops.object.text_add()
        text_obj = bpy.context.active_object
        if label != "" or label is not None:
            text_obj.data.body = label
            text_obj.data.size = 0.1
            text_obj.data.align_x = 'CENTER'
            text_obj.name = f"{label}"
            text_obj.rotation_euler = (1.5707, 0, 0)
            bpy.ops.object.convert(target='MESH')
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.dissolve_limited(angle_limit=0.05)
            bpy.ops.object.mode_set(mode='OBJECT')

            

    shape_obj = bpy.context.active_object
    shape_obj.name = name

    # Apply transformations
    shape_obj.scale = scale
    
    shape_obj.rotation_euler = rotation
    bpy.ops.object.transform_apply(scale=True, rotation=True, location=False)
    #Delete only faces
    if delete_faces:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.delete(type='ONLY_FACE')
        bpy.ops.object.mode_set(mode='OBJECT')
    
    # Move to a hidden collection so it doesnt clutter the scene
    shape_collection = bpy.data.collections.get("BoneShapes")
    if not shape_collection:
        shape_collection = bpy.data.collections.new("BoneShapes")
        bpy.context.scene.collection.children.link(shape_collection)
    
    # Unlink from current collection and move to BoneShapes and add to Temp Drawing collection
    for col in shape_obj.users_collection:
        col.objects.unlink(shape_obj)
    shape_collection.objects.link(shape_obj)
    
    return shape_obj


def setup_control_board_shapes(armature):
    main_collection = bpy.data.collections.get("Temp Drawing Collection")
    shape_collection = bpy.data.collections.get("BoneShapes")
    if not shape_collection:
        shape_collection = bpy.data.collections.new("BoneShapes")
    if main_collection and shape_collection.name not in main_collection.children:
        main_collection.children.link(shape_collection)
        
    
    layer_collection = bpy.context.scene.view_layers[0].layer_collection
    temp_layer = layer_collection.children.get("Temp Drawing Collection")
    if temp_layer:
        bone_shapes_layer = temp_layer.children.get("BoneShapes")
    if bone_shapes_layer:
        bone_shapes_layer.exclude = True
        
    
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')

    # Define bones and their shapes/labels
    control_bones = {
        
        "Face_Main_Control_Board": {
            "shape": "SQUARE",
            "label": "Face Control Board",
            "label_scale": (0.5, 0.5, 0.5),
            "color": (0.3, 0.8, 0.3, 1),  # green
            "location": (.5, 0, .24),
            "scale": (.5, .4, 1),
            "rotation": (0, 0, 0),  
        },  
        "Label_Face_Main_Control_Board": {
            "shape": "TEXT",
            "label": "Face Control Board",
            "label_scale": (0.2, 0.2, 0.2),
            "color": (0,0,0, 1),  # black
            "location": (.5, 0, .1),
            "scale": (.5, .5, .5),
            "rotation": (0,  0, 0),

        },
        "Face_Mouth_Canvas": {
            "shape": "SQUARE",
            "label": "Mouth Control",
            "label_scale": (0.2, 0.2, 0.2),
            "color": (0.3, 0.3, 1, 1),  # blue
            "location": (.4, 0, -.015),
            "scale": (0.48, 0.3, .3),
            "rotation": (0, 0, 0),
        },
        "Label_Mouth_Position_Control": {
            "shape": "TEXT",
            "label": "Mouth Position",
            "label_scale": (0.1, 0.1, 0.1),
            "color": (0.3, 0.3, 1, 1),  # blue
            "location": (.4, 0, -.015),
            "scale": (0.3, 0.3, .3),
            "rotation": (0, 0, 0),
            
        },
        "Face_Mouth_Position_Control": {
            "shape": "SQUARE",
            "color": (1, 0.3, 0.3, 1),
            "location": (.5, 0, .24),
            "scale": (0.1, 0.06, 0),
            "rotation": (0, 0, 0),
            "delete_faces": False,
        },
        
        "Hook_Mouth_Top_L": {
            "shape": "ARROW",
            "color": (0.3, 0.3, 1, 1),  # blue
            "scale": (.08, .08, .08),
        },
        "Hook_Mouth_Top_R": {
            "shape": "ARROW",
            "color": (0.3, 0.3, 1, 1),  # blue
            "scale": (.08, .08, .08),
        },
        "Hook_Mouth_Top_C": {
            "shape": "ARROW",
            "color": (0.3, 0.3, 1, 1),  # blue
            "scale": (.08, .08, .08),
        },
        "Hook_Mouth_Bot_L": {
            "shape": "ARROW",
            "color": (0.3, 0.3, 1, 1),  # blue
            "scale": (.08, .08, .08),
        },
        "Hook_Mouth_Bot_R": {
            "shape": "ARROW",
            "color": (0.3, 0.3, 1, 1),  # blue
            "scale": (.08, .08, .08),
        },
        "Hook_Mouth_Bot_C": {
            "shape": "ARROW",
            "color": (0.3, 0.3, 1, 1),  # blue
            "scale": (.08, .08, .08),
        },
        
    }

    for bone_name, settings in control_bones.items():
        pose_bone = armature.pose.bones.get(bone_name)
        if not pose_bone:
            continue

        # Create and assign custom shape
        shape_obj = create_bone_shape(
            f"Shape_{bone_name}", 
            settings["shape"],
            settings.get("scale", (0.1, 0.1, 0.1)),
            settings.get("rotation", (0, 0, 0)),
            settings.get("delete_faces", True),
            settings.get("label", None)
        )
        pose_bone.custom_shape = shape_obj
        pose_bone.use_custom_shape_bone_size = False  


        # Set bone color group
        pose_bone.color.palette = 'CUSTOM'
        pose_bone.color.custom.normal = settings["color"][:3]
 

    


# Might have to break these into separate classes for each element
class CreateRig(bpy.types.Operator):
    """Create the face rig based on the drawn mouth shapes and control board"""
    bl_idname = "object.create_rig"
    bl_label = "Create Rig"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    rig_name: bpy.props.StringProperty(name="Rig Name", default="Character")
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    bone_definitions={
        "GP Face Rig Root": {
            "head": (0, .2, 0),
            "tail": (0, .2, .25),
            "deform": True,
        },
        "GP Mouth Bone": {
            "head": (0, 0, -0.05),
            "tail": (0, 0, 0.05),
            "deform": True,
        },
        "shape_board": {
            "head": (0, 0, 0),
            "tail": (0, 0, 0.2),
            "deform": False,
        },
        "Face_Main_Control_Board": {
            "head": (.5,    0, .1),
            "tail": (.5, 0, .3),
            "deform": False,
        },
        "Label_Face_Main_Control_Board": {
            "head": (.5, 0, .3),
            "tail": (.5, 0, .5),
            "deform": False,
        },
        "Face_Mouth_Canvas": {
            "head": (.5, 0, .06),
            "tail": (.5, 0, .11),
            "deform": False,    
        },
        "Face_Mouth_Position_Control": {
            "head": (.5, 0, .06),
            "tail": (.5, 0, .11),
            "deform": False,
        },
        
        "Label_Mouth_Position_Control": {
            "head": (.36, 0, .22),
            "tail": (.36, 0, .32),
            "deform": False,
        },
        
        # These will hold relative distances from the Face_Mouth_Position_Control bone that the hooks will be constrained to, so they dont need to be in exact positions yet, just in the general area of the mouth and evenly spaced.
        "Hook_Mouth_Top_L": {
            "head": (.1, 0, .1),
            "tail": (.1, 0, 0.15),
            "deform": True,
        },
        "Hook_Mouth_Top_C": {
            "head": (0, 0,  .1),
            "tail": (0, 0, 0.15),
            "deform": True,
        },
        "Hook_Mouth_Top_R": {
            "head": (-.1, 0,  .1),
            "tail": (-.1, 0, 0.15),
            "deform": True,
        },
        "Hook_Mouth_Bot_L": {
            "head": (.1, 0, -.1),
            "tail": (.1, 0, -.15),
            "deform": True,
        },
        "Hook_Mouth_Bot_C": {
            "head": (0, 0, -.1),
            "tail": (0, 0, -.15),
            "deform": True,
        },
        "Hook_Mouth_Bot_R": {
            "head": (-.1, 0, -.1),
            "tail": (-.1, 0, -.15),
            "deform": True,
        },
           
    }
        
    
    
    @classmethod
    def poll(cls, context):
        # Ensure there's an active Grease Pencil object and it has an ID
        gp_obj = context.active_object
        if gp_obj and gp_obj.type == 'GREASEPENCIL':
            vgroup_name = "GP Mouth Bone"
            return vgroup_name in gp_obj.vertex_groups
        return False
        

    

    def execute(self, context):
        rig_id = generate_unique_id()
############################### Widget Creation/Import and Organization #######################




############################### Face Control Board Creation ################################        
        
        
        
        
################################ Mouth Rig Creation ########################################

        # Get the active object
        gp_obj = context.active_object
        tag_rig_object(gp_obj, rig_id, "Grease Pencil Main Shape")
        if gp_obj and gp_obj.type == 'GREASEPENCIL':
            vgroup_name = "GP Mouth Bone"
            if vgroup_name not in gp_obj.vertex_groups:
                self.report({'ERROR'}, f"Vertex group '{vgroup_name}' not found.")
                return {'CANCELLED'}
        else:
            self.report({'ERROR'}, "Active object is not a Grease Pencil object.")
            return {'CANCELLED'}   
        # Retrieve control board and puck locations
        collection_name = "Mouth Rig Control Board Objects"
        collection = bpy.data.collections.get(collection_name)
            


        
        bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
        armature = context.object
        armature.name = "GP_Rig"
        arm_data = armature.data
        tag_rig_object(armature, rig_id, "Main Armature")
        bpy.ops.object.mode_set(mode='EDIT')

        # Access the armature's edit bones
        bones = armature.data.edit_bones
        #Create bone collections
        bpy.ops.object.mode_set(mode='EDIT')
        if "Bones" in arm_data.collections:
            arm_data.collections.remove(arm_data.collections.get("Bones"))
        if "Face" not in arm_data.collections:
            face_coll = arm_data.collections.new("Face")
        else:
            face_coll = arm_data.collections["Face"]
        mouth_coll = arm_data.collections.new("Mouth Bones", parent = face_coll)
        eyes_coll = arm_data.collections.new("Eyes Bones", parent =face_coll)
        nose_coll = arm_data.collections.new("Nose Bones", parent =face_coll)
        hid_coll = arm_data.collections.new("Hidden Bones", parent =face_coll)
        hid_coll.is_visible=False
        hid_mouth_coll = arm_data.collections.new("Hidden Mouth Bones", parent =hid_coll)
        hid_eyes_coll = arm_data.collections.new("Hidden Eyes Bones", parent =hid_coll)
        hid_brows_coll = arm_data.collections.new("Hidden Eyebrow Bones", parent =hid_coll)
        hid_nose_coll = arm_data.collections.new("Hidden Nose Bones", parent =hid_coll)
        

        # Create the root bone, it's slightly offset
        # from the mouth to be in the center of the head it'll join with
        root_bone = bones[0]
        root_bone.name = "GP Face Rig Root"
        root_bone.head = self.bone_definitions["GP Face Rig Root"]["head"]
        root_bone.tail = self.bone_definitions["GP Face Rig Root"]["tail"]
        face_coll.assign(root_bone)

        # Create the named bone and place it in middle of Lattice
        
        gp_obj = context.active_object
        if gp_obj and gp_obj.type == 'GREASEPENCIL':
            vgroup_name = "GP Mouth Bone"
        named_bone = bones.new(vgroup_name)
        named_bone.head = (0, 0, -0.05)
        named_bone.tail = (0, 0, 0.05)
        named_bone.parent = root_bone
        named_bone.use_connect = False
        
        hid_mouth_coll.assign(named_bone)
        
        # Retrieve control board and puck locations
        collection_name = "Mouth Rig Control Board Objects"
        collection = bpy.data.collections.get(collection_name)

        if collection is None:
            self.report({'ERROR'}, f"Collection '{collection_name}' not found.")
            return {'CANCELLED'}

        shape_board = None
        puck = None
        for obj in collection.objects:
            if obj.name == "Mouth Shapes Control Plane":
                
                shape_board = obj
                obj.hide_viewport = True
            elif obj.name == "Mouth Shape Control Selector":
                puck = obj
                puck.hide_viewport =True
            
        if not shape_board or not puck:
            self.report({'ERROR'}, "Shape board or Selector not found in the collection.")
            return {'CANCELLED'}
        
        
        
        
        # Create the control board bone
        shape_board_bone = bones.new("shape_board_bone")
        shape_board_bone.head = shape_board.location
        shape_board_bone.tail = (shape_board.location.x, shape_board.location.y, shape_board.location.z + shape_board.scale.z)
        shape_board_bone.parent = root_bone
        shape_board_bone.use_connect = False
        shape_board_bone.use_deform = False
        shape_board_bone.show_wire = True
        mouth_coll.assign(shape_board_bone)
        
        # Create the puck control bone
        mouth_puck_control_bone = bones.new("mouth_puck_control")
        mouth_puck_control_bone.head = puck.location
        mouth_puck_control_bone.tail = (puck.location.x, puck.location.y, puck.location.z + 0.2)
        mouth_puck_control_bone.parent = shape_board_bone
        mouth_puck_control_bone.use_connect = False
        mouth_coll.assign(mouth_puck_control_bone)
        
        #Create Bones for each GP object in the other collection and set them to hide
        bone_names = []
        for obj in collection.objects:
            if obj.type== 'GREASEPENCIL':
                bone_names.append(obj.name)
                
        
        if collection and armature and armature.type == 'ARMATURE':
            bpy.context.view_layer.objects.active = armature
            bpy.ops.object.mode_set(mode='EDIT')
            arm_data = armature.data
    
            shape_board_bone = arm_data.edit_bones.get("shape_board_bone")
    
        for obj in collection.objects:
            if obj.type == 'GREASEPENCIL':
                bone_name = f"{obj.name}_Shape_Bone"
                print(f"Creating bone for: {bone_name}")
            
                bone = arm_data.edit_bones.new(bone_name)
                bone.head = obj.location
                bone.tail = (obj.location.x, obj.location.y, obj.location.z + 0.2)
                hid_mouth_coll.assign(arm_data.edit_bones.get(bone_name)) 
                #add shrinkwrap to each bone to the control board
#                bpy.ops.object.mode_set(mode='POSE')
#                pose_bones = armature.pose.bones
#                pose_bone_mouth_shape = pose_bones[bone_name]
#                shrinkwrap = pose_bone_mouth_shape.constraints.new('SHRINKWRAP')
#                shrinkwrap.target = control_board
#                shrinkwrap.wrap_mode = 'ON_SURFACE'
#                bpy.ops.object.mode_set(mode='EDIT')
            
            if shape_board_bone:
                bone.parent = shape_board_bone
    
    # back to object mode
        bpy.ops.object.mode_set(mode='OBJECT')
    
        
    
    # now add constraints in Object mode
        for obj in collection.objects:
            if obj.type == 'GREASEPENCIL':
                bone_name = f"{obj.name}_Shape_Bone"
            
                constraint = obj.constraints.new('CHILD_OF')
                constraint.target = armature
                constraint.subtarget = bone_name
            
        
                bpy.context.view_layer.objects.active = obj
                bpy.ops.constraint.childof_set_inverse(constraint=constraint.name, owner='OBJECT')
            if obj.name == "Mouth Shapes Control Plane":
                constraint = obj.constraints.new('CHILD_OF')
                bone_name = "shape_board_bone"
                constraint.target = armature
                constraint.subtarget = bone_name
                bpy.ops.constraint.childof_set_inverse(constraint=constraint.name, owner='OBJECT')
                

        bpy.context.view_layer.update()
        print("All bones created and constraints added.")

                

    
                  
        # Switch back to the armature
        bpy.context.view_layer.objects.active = armature  
        # Switch to pose mode to set custom shapes & visbility rules
        bpy.ops.object.mode_set(mode='POSE')
        # Access the pose bones
        pose_bones = armature.pose.bones
        # Set custom shapes (ensure you have created custom bone shapes named 'ControlBoardShape' and 'PuckShape')
        if 'Mouth Shapes Control Plane' in bpy.data.objects:
            shape_board_bone_obj = pose_bones["shape_board_bone"]
            shape_board_bone_obj.custom_shape = bpy.data.objects['Mouth Shapes Control Plane']
            
            shape_board_bone_obj.use_custom_shape_bone_size = False
            #for child_bone in shape_board_bone_obj.children:
                # child_bone.bone.hide = True

        if 'Mouth Shape Control Selector' in bpy.data.objects:
            mouth_puck_control_bone_obj = pose_bones["mouth_puck_control"]
            mouth_puck_control_bone_obj.custom_shape = bpy.data.objects['Mouth Shape Control Selector']
            mouth_puck_control_bone_obj.use_custom_shape_bone_size = False
            mouth_puck_control_bone_obj.bone.hide = False
        
        # Add shrinkwrap constraint to the puck bone
        shrinkwrap = mouth_puck_control_bone_obj.constraints.new('SHRINKWRAP')
        shrinkwrap.target = shape_board
        shrinkwrap.wrap_mode = 'ON_SURFACE'
        # shrinkwrap.use_keep_above_surface = True

        # Switch back to object mode
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        

        # Parent the GP object to the armature with weights previously defined
        # Might not need this? Seems to work without parenting, but keeping here just in case
        # gp_obj = bpy.data.objects["GP Temp Face Object"]
        # gp_obj.select_set(True)
        # gp_obj.parent = armature
        # gp_obj.parent_type = 'ARMATURE'
        # arm_mod = gp_obj.modifiers.new(name="ArmatureDeform", type='GREASE_PENCIL_ARMATURE')
        # arm_mod.object = armature
        # arm_mod.use_vertex_groups = True
        

        # Set up drivers for layer visibility using bones
        gp_obj = bpy.data.objects["GP Temp Face Object"]
        gp_obj.select_set(True)
        
        for layer in gp_obj.data.layers:
            for bone_name in bone_names:
                
                layer_pattern = re.compile(f"^{re.escape(bone_name.replace(' Shape Bone', ''))}(\\.\\d+)?$")
                bone_name = bone_name + "_Shape_Bone"
                if layer_pattern.match(layer.name):
                    driver = layer.driver_add("hide").driver
                    driver.type = 'SCRIPTED'
                
                    var1 = driver.variables.new()
                    var1.name = "puck_x"
                    var1.type = 'TRANSFORMS'
                    var1.targets[0].id = armature
                    var1.targets[0].bone_target = "mouth_puck_control"
                    var1.targets[0].transform_type = 'LOC_X'
                    var1.targets[0].transform_space = 'WORLD_SPACE'
                    
                    var2 = driver.variables.new()
                    var2.name = "bone_x"
                    var2.type = 'TRANSFORMS'
                    var2.targets[0].id = armature
                    var2.targets[0].bone_target = bone_name
                    var2.targets[0].transform_type = 'LOC_X'
                    var2.targets[0].transform_space = 'WORLD_SPACE'
                    
                    var3 = driver.variables.new()
                    var3.name = "puck_z"
                    var3.type = 'TRANSFORMS'
                    var3.targets[0].id = armature
                    var3.targets[0].bone_target = "mouth_puck_control"
                    var3.targets[0].transform_type = 'LOC_Z'
                    var3.targets[0].transform_space = 'WORLD_SPACE'
                    
                    var4 = driver.variables.new()
                    var4.name = "bone_z"
                    var4.type = 'TRANSFORMS'
                    var4.targets[0].id = armature
                    var4.targets[0].bone_target = bone_name
                    var4.targets[0].transform_type = 'LOC_Z'
                    var4.targets[0].transform_space = 'WORLD_SPACE'
                    
                    driver.expression = "(abs(puck_x - bone_x) > 0.1) or (abs(puck_z - bone_z) > 0.1)"
                    

   

        
         # Ensure the control board and puck bones follow the objects
        shape_board_bone_obj = armature.pose.bones["shape_board_bone"]
        mouth_puck_control_bone_obj = armature.pose.bones["mouth_puck_control"]
        
        childof_puck = puck.constraints.new('CHILD_OF')
        childof_puck.target = armature
        childof_puck.subtarget = "mouth_puck_control"
        

        # Add the armature to the same collection as the Grease Pencil object
        collection = gp_obj.users_collection[0]
        if armature.users_collection:
            for coll in armature.users_collection:
                coll.objects.unlink(armature)
            collection.objects.link(armature)
            
        # Find the lattice object and add a CHILD_OF constraint to it
        lattice = bpy.data.objects.get("GPMouthLattice")
        if lattice:
            tag_rig_object(lattice, rig_id, "Mouth Lattice")
            lattice_constraint = lattice.constraints.new(type =  'CHILD_OF')
            lattice_constraint.target = bpy.data.objects["GP_Rig"]
            
            #lattice_constraint.subtarget = "GP Mouth Bone" uneeded for some reason
        # Create bones for lattice and assign vertex groups to vertices to mouth bone - set to linear -- actually bspline is fine 
            hook_map = build_mouth_hook_map()
            bpy.context.view_layer.objects.active = armature
            bpy.ops.object.mode_set(mode='EDIT')
            
            edit_bones = armature.data.edit_bones
            
            #Direct Lattice Control Bones
            bone_positions = {
            
                "Mouth_Top_L":     ((.08, 0, .02), (.08, 0, 0.04)),
                "Mouth_Top_C":     ((0, 0, .02),    (0, 0, 0.04)),
                "Mouth_Top_R":     ((-.08, 0, .02),  (-.08, 0, 0.04)),
                "Mouth_Bot_L":     ((.08, 0, -.04), (.08, 0, -0.02)),
                "Mouth_Bot_C":     ((0, 0, -.04),    (0, 0, -0.02)),
                "Mouth_Bot_R":     ((-.08, 0, -.04),  (-.08, 0, -0.02)),
                #"Mouth_Depth":     ((0, 0, -0.3), (0, 0, 0.4)), -
            
            }

            for bone_name, (head, tail) in bone_positions.items():
                if bone_name not in edit_bones:
                    bone = edit_bones.new(bone_name)
                    bone.head = head
                    bone.tail = tail
                    bone.parent = edit_bones.get("GP Mouth Bone")  # parent to existing mouth bone
                    hid_mouth_coll.assign(bone)
                    

            bpy.ops.object.mode_set(mode='OBJECT')

            # --- Step 1: Add hook modifiers to the lattice per vertex group ---
            bpy.context.view_layer.objects.active = lattice
            
            x = 0

            for bone_name, vert_indices in hook_map.items():
                
                # Create a vertex group for these vertices
                vg = lattice.vertex_groups.new(name=bone_name)
                vg.add(vert_indices, 1.0, 'REPLACE')

                # Add hook modifier pointing to the armature bone
                hook_mod = lattice.modifiers.new(name=f"Hook_{bone_name}", type='HOOK')
                hook_mod.object = armature
                hook_mod.subtarget = bone_name          # the specific bone
                hook_mod.vertex_group = bone_name       # only affects these verts
                
                
            # # --- Step 2: Set lattice interpolation to linear ---
            # lattice.data.interpolation_type_u = 'KEY_LINEAR'
            # lattice.data.interpolation_type_v = 'KEY_LINEAR'
            # lattice.data.interpolation_type_w = 'KEY_LINEAR'
            
            #bpy.ops.object.modifier_add(type='GREASE_PENCIL_THICKNESS')

            # --- Step 3: Add a modifier to the GP object to scale thickness corecctly using a driven value
        thick_mod = gp_obj.modifiers.new(
            name="BoneThickness", 
            type='GREASE_PENCIL_THICKNESS'
        )
        thick_mod.thickness_factor = 1.0  # start at 1.0 

        # Drive the thickness factor from the bone scale
        fcurve = thick_mod.driver_add("thickness_factor")
        driver = fcurve.driver
        driver.type = 'SCRIPTED'

        var = driver.variables.new()
        var.name = "s"
        var.type = 'TRANSFORMS'

        target = var.targets[0]
        target.id = armature
        target.bone_target = "GP Mouth Bone"
        target.transform_type = 'SCALE_AVG'
        target.transform_space = 'LOCAL_SPACE'

        driver.expression = "s"
    
            
        # lattice_constraint.childof_set_inverse(constraint="Child Of", owner='OBJECT')
        ##### Create Mouth Face Rig Control Panel #####
        #Create control bones
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='EDIT')
        #Main control Board
        main_control_bone = edit_bones.new("Face_Main_Control_Board")
        main_control_bone.head = self.bone_definitions["Face_Main_Control_Board"]["head"]
        main_control_bone.tail = self.bone_definitions["Face_Main_Control_Board"]["tail"]
        main_control_bone.parent = edit_bones.get("GP Face Rig Root")
        main_control_bone.use_connect = False
        mouth_coll.assign(main_control_bone)
        
        #Main Control Board Label
        main_control_label_bone = edit_bones.new("Label_Face_Main_Control_Board")
        main_control_label_bone.head = self.bone_definitions["Label_Face_Main_Control_Board"]["head"]
        main_control_label_bone.tail = self.bone_definitions["Label_Face_Main_Control_Board"]["tail"]
        main_control_label_bone.parent = edit_bones.get("Face_Main_Control_Board")
        main_control_label_bone.use_connect = False
        mouth_coll.assign(main_control_label_bone)
        
        #Canvas bone
        mouth_position_canvas_bone = edit_bones.new("Face_Mouth_Canvas")
        mouth_position_canvas_bone.head = self.bone_definitions["Face_Mouth_Canvas"]["head"]
        mouth_position_canvas_bone.tail = self.bone_definitions["Face_Mouth_Canvas"]["tail"]
        mouth_position_canvas_bone.parent = main_control_bone
        mouth_position_canvas_bone.use_connect = False
        mouth_coll.assign(mouth_position_canvas_bone)
        
        
        #Mouth position controller
        mouth_position_control_bone = edit_bones.new("Face_Mouth_Position_Control")
        mouth_position_control_bone.head = self.bone_definitions["Face_Mouth_Position_Control"]["head"]
        mouth_position_control_bone.tail = self.bone_definitions["Face_Mouth_Position_Control"]["tail"] 
        mouth_position_control_bone.parent = mouth_position_canvas_bone
        mouth_position_control_bone.use_connect = False
        mouth_coll.assign(mouth_position_control_bone)
        
        #Mouth Position Label Bone
        mouth_label_bone = edit_bones.new("Label_Mouth_Position_Control")
        mouth_label_bone.head = self.bone_definitions["Label_Mouth_Position_Control"]["head"]
        mouth_label_bone.tail = self.bone_definitions["Label_Mouth_Position_Control"]["tail"]
        mouth_label_bone.parent = mouth_position_canvas_bone
        mouth_label_bone.use_connect = False
        mouth_coll.assign(mouth_label_bone)
        
        

        bpy.ops.object.mode_set(mode='POSE')
        mouth_pose_bone = armature.pose.bones.get("GP Mouth Bone")
        copy_transform = mouth_pose_bone.constraints.new('COPY_TRANSFORMS')
        copy_transform.target = armature
        copy_transform.subtarget = "Face_Mouth_Position_Control"
        copy_transform.mix_mode = 'AFTER_SPLIT'
        copy_transform.target_space = 'LOCAL_OWNER_ORIENT'
        copy_transform.owner_space = 'LOCAL_WITH_PARENT'
        
        control_hook_bone_positions = {
        
            "Mouth_Top_L":     (self.bone_definitions["Hook_Mouth_Top_L"]["head"], self.bone_definitions["Hook_Mouth_Top_L"]["tail"]),
            "Mouth_Top_C":     (self.bone_definitions["Hook_Mouth_Top_C"]["head"], self.bone_definitions["Hook_Mouth_Top_C"]["tail"]),
            "Mouth_Top_R":     (self.bone_definitions["Hook_Mouth_Top_R"]["head"], self.bone_definitions["Hook_Mouth_Top_R"]["tail"]),
            "Mouth_Bot_L":     (self.bone_definitions["Hook_Mouth_Bot_L"]["head"], self.bone_definitions["Hook_Mouth_Bot_L"]["tail"]),
            "Mouth_Bot_C":     (self.bone_definitions["Hook_Mouth_Bot_C"]["head"], self.bone_definitions["Hook_Mouth_Bot_C"]["tail"]),
            "Mouth_Bot_R":     (self.bone_definitions["Hook_Mouth_Bot_R"]["head"], self.bone_definitions["Hook_Mouth_Bot_R"]["tail"]),
            #"Mouth_Depth":     ((0, 0, -0.3), (0, 0, 0.4)), -
        
        }
        
        for bone_name, (head, tail) in control_hook_bone_positions.items():
            bpy.ops.object.mode_set(mode='EDIT')
            hook_control_bone_name = bone_name.replace("Mouth_", "Hook_Mouth_")
            if hook_control_bone_name not in edit_bones:
                bone = edit_bones.new(hook_control_bone_name)
                # Get relative positions and add them to the Face_Mouth_Position_Control bone's head and tail positions
                head = tuple(Vector(head) + Vector((self.bone_definitions["Face_Mouth_Position_Control"]["head"])))
                tail = tuple(Vector(tail) + Vector((self.bone_definitions["Face_Mouth_Position_Control"]["tail"])))
                bone.head = head 
                bone.tail = tail
                bone.parent = edit_bones.get("Face_Mouth_Position_Control")  
                mouth_coll.assign(bone)
                bpy.ops.object.mode_set(mode='POSE')
                # Add a copy transforms constraint to the helper controls for each of these bones
                pose_bone = armature.pose.bones.get(bone_name)
                copy_transforms = pose_bone.constraints.new('COPY_TRANSFORMS')
                copy_transforms.target = armature
                copy_transforms.subtarget = hook_control_bone_name
                copy_transforms.mix_mode = 'AFTER_SPLIT'
                copy_transforms.target_space = 'LOCAL_OWNER_ORIENT'
                copy_transforms.owner_space = 'LOCAL_WITH_PARENT'
        
        #Clean up: Delete all helper objects, change collection names, reset modes, and parent the armature to the main control board
        setup_control_board_shapes(armature)
        
        main_drawing_collection = bpy.data.collections.get("Temp Drawing Collection") 
        main_drawing_collection.name = "GP Face Rig Drawing Collection"
        context.scene.has_setup_been_run = False
        context.scene.gp_face_mode = 'NONE'
        obj = bpy.data.objects.get("GP Temp Face Object")
        if obj:
            obj.name = "GP Face Rig Main Mouth"
            obj.parent = armature
        
        deleteobj = bpy.data.objects.get("Target Face Drawing Plane")
        if deleteobj:
            bpy.data.objects.remove(deleteobj, do_unlink=True)
        collection = bpy.data.collections.get("Mouth Rig Control Board Objects")
        shapecollection = bpy.data.collections.get("BoneShapes")
        moveobj = bpy.data.objects.get("Mouth Shapes Control Plane")
        if moveobj:
            collection.objects.unlink(moveobj)
            shapecollection.objects.link(moveobj)
        moveobj = bpy.data.objects.get("Mouth Shape Control Selector")
        if moveobj:
            collection.objects.unlink(moveobj)
            shapecollection.objects.link(moveobj)
        for obj in collection.objects:
            if obj.type == 'GREASEPENCIL':
                obj.hide_select = True
            # Parent the armature to the main control board bone
        armature.name = "GP Mouth Rig"
        context.scene.rig_created = True
        face_rig = find_rig(context)
        if not face_rig:
            self.report({'ERROR'}, "No valid face rig found.")
            return {'CANCELLED'}
    
        name = self.rig_name
        settings = context.scene.grease_pencil_face_rig_settings
        settings.rig_name = name
    
        renames = {
            "GP Mouth Rig": f"{name}_Mouth_Rig",
            "Mouth Shapes Control Plane": f"{name}_Mouth_Shapes_Control_Plane",
            "Mouth Shape Control Selector": f"{name}_Mouth_Shape_Control_Selector",
            "GP Face Rig Drawing Collection": f"{name}_Face_Rig_Collection",
            "Mouth Rig Control Board Objects": f"{name}_Control_Board_Collection",
            "BoneShapes": f"{name}_BoneShapes",
            "GPMouthLattice": f"{name}_Mouth_Lattice",
        }
    
        for old_name, new_name in renames.items():
            obj = bpy.data.objects.get(old_name)
            if obj:
                obj.name = new_name
                self.report({'INFO'}, f"Renamed {old_name} to {new_name}")
            
        for col in bpy.data.collections:
            if col.name in renames:
                col.name = renames[col.name]
                
        self.report({'INFO'}, "Rig successfully created.")
        return {'FINISHED'}
        
        
class MY_OT_apply_shrinkwrap(bpy.types.Operator):
    """Bind the face rig to a 3D object using the vertex group created from the grease pencil layers"""
    bl_idname = "my.apply_shrinkwrap"
    bl_label = "Apply Shrinkwrap"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.shrinkwrap_settings
    
        
        lattice = settings.target_lattice
        
        if not lattice:
            self.report({'ERROR'}, f"Lattice object '{name}_Mouth_Lattice' not found.")
            return {'CANCELLED'}
        if not settings.target_object:
            self.report({'ERROR'}, "No target object selected.")
            return {'CANCELLED'}
        mod = lattice.modifiers.new(name="MouthShrinkwrap", type='SHRINKWRAP')
        mod.target = settings.target_object
        mod.wrap_method = settings.wrap_method
        mod.wrap_mode = settings.wrap_mode
        mod.offset = settings.offset
        #Legacy
        if settings.wrap_method == 'PROJECT':
            mod.use_negative_direction = settings.use_negative_direction
            mod.use_positive_direction = settings.use_positive_direction
        bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)  # Move to top of stack
            
        return {'FINISHED'}
    
    def update_shrinkwrap(self, context):
    
        lattice = bpy.data.objects.get("GPMouthLattice")
        mod = lattice.modifiers.get("ShrinkwrapToFace") if lattice else None
        if mod:
            mod.offset = self.offset

        offset: bpy.props.FloatProperty(
            name="Offset",
            default=0.0,
            update=update_shrinkwrap  # fires every time the value changes
        )
        
        
    
class MY_OT_onion_navigate(bpy.types.Operator):
    bl_idname = "my.onion_navigate"
    bl_label = "Navigate Onion Skin"
    bl_options = {'REGISTER', 'UNDO'}
    
    direction: bpy.props.IntProperty(name = "Direction", default=1)  # 1 for forward, -1 for backward
    def execute(self, context):
        settings = context.scene.grease_pencil_face_rig_settings
        collection = bpy.data.collections.get("Mouth Rig Control Board Objects")
        if not collection:
            self.report({'ERROR'}, "Collection 'Mouth Rig Control Board Objects' not found.")
            return {'CANCELLED'}
        gp_duplicates = [obj for obj in collection.objects if obj.type == 'GREASEPENCIL']
        
        new_index = settings.onion_preview_index + self.direction
        settings.onion_preview_index = max(0, min(new_index, len(gp_duplicates) - 1))
        
        return {'FINISHED'}
    

class MY_OT_append_to_rig_permanent(bpy.types.Operator):
    bl_idname = "my.append_to_rig"
    bl_label = "Append to Rig"
    bl_options = {'REGISTER', 'UNDO'}
    # This will permanently join the face rig to the target rig, making sure all relationships are maintained
    
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)
    
    
    
    def execute(self, context):
        settings = context.scene.grease_pencil_face_rig_settings
        face_rig = context.scene.target_rig_settings.face_rig
        # Get character namer from rig so that we cna get teh lattice 
        rig_id = get_rig_id(face_rig)
        lattice = get_rig_object_by_role(rig_id, "Mouth Lattice")
        gp_obj = get_rig_object_by_role(rig_id, "Grease Pencil Main Shape")
        self.report({'INFO'}, f"Found lattice: {lattice.name}")
        if not face_rig:
            self.report({'ERROR'}, "No valid face rig found to append to.")
            return {'CANCELLED'}
        target_rig = context.scene.target_rig_settings.target_rig
        head_bone_name = context.scene.target_rig_settings.head_bone_name
        tag_rig_object(target_rig, rig_id, "Target Rig")
        
        #Get my collections
        bone_collections = [col.name for col in face_rig.data.collections]
        for col in bone_collections:
            if col in target_rig.data.collections:
                pass
            else:
                new_col = target_rig.data.collections.new(col)
                self.report({'INFO'}, f"Created collection {col} in target rig")
        
        
        #The lattice object is not binding well -- rotation axis is strange when moving the head bone
        

        bone = target_rig.data.bones.get(head_bone_name)
        if not bone:
            self.report({'ERROR'}, f"Bone '{head_bone_name}' not found")
            return {'CANCELLED'}

        
        pose_bone = target_rig.pose.bones.get(head_bone_name)
        if pose_bone:
            # Convert bone head position to world space
            head_world = target_rig.matrix_world @ pose_bone.head
            tail_world = target_rig.matrix_world @ pose_bone.tail
        else:
            head_world = target_rig.location
            tail_world = target_rig.location

        face_rig.location = head_world
        # Push the these locations by a little on the y axis
        lattice.location = head_world 
        
        gp_obj.location = head_world 
        self.report({'INFO'}, f"Positioned face rig at head bone location: {head_world}")
        
        
        bpy.ops.object.select_all(action='DESELECT')
        face_rig.select_set(True)
        target_rig.select_set(True)
        context.view_layer.objects.active = target_rig
        bpy.ops.object.join()  # Join the rigs together
        bpy.ops.object.mode_set(mode='EDIT')
        target_rig.data.edit_bones["GP Face Rig Root"].head = head_world
        target_rig.data.edit_bones["GP Face Rig Root"].tail = tail_world
        target_rig.data.edit_bones["GP Face Rig Root"].parent = target_rig.data.edit_bones[head_bone_name]
        target_rig.data.edit_bones["GP Face Rig Root"].use_connect = False
        bpy.ops.object.mode_set(mode='POSE')
        target_rig.data.bones["GP Face Rig Root"].display_type = 'STICK'
        bpy.ops.object.mode_set(mode='OBJECT')
        
        
        lattice_modifiers = lattice.modifiers
        for mod in lattice_modifiers:
            if mod.type == 'HOOK':
                mod.object = target_rig
        
        
        # GP Face Rig Root --> parented to head bone -- move via object mode or pose mode? or edit mode? or add copy transforms constraint to head bone with offset? or just delete and set the head bone as root??
        # Lattice --> Constraint works its fine
            # The gp object and the lattice resets position to origin? -- Need to place them by the new face rig root bone position
        # All lattice hooks need to be re-targeted to the new rig
        # Collections arent maintained????? maybe we need to create new collections in the target rig and move objects there? 
        
        
        # bpy.ops.object.join()
        
        
        
        #self.report({'INFO'}, "Append to Rig functionality not implemented yet.")
        return {'FINISHED'}
    
    
    
class MY_OT_append_to_rig_simple(bpy.types.Operator):
    bl_idname = "my.append_to_rig_simple"
    bl_label = "Append to Rig (Simple)"
    bl_options = {'REGISTER', 'UNDO'}
    # This is will append using constrains only, instead of joining rigs
    
    def execute(self, context):
        face_rig = context.scene.target_rig_settings.face_rig
        target_rig = context.scene.target_rig_settings.target_rig
        if not face_rig or not target_rig:
            self.report({'ERROR'}, "Face rig or target rig not set.")
            return {'CANCELLED'}
        
        bpy.ops.object.select_all(action='DESELECT')
        face_rig.select_set(True)
        target_rig.select_set(True)
        context.view_layer.objects.active = target_rig
        bpy.ops.object.join()  # Join the rigs together
        
        self.report({'INFO'}, "Rigs joined together. You may need to reposition the combined rig and reassign constraints manually.")
        return {'FINISHED'}
class MY_OT_enter_edit_mode(bpy.types.Operator):
    bl_idname = "my.enter_edit_mode"
    bl_label = "Enter Edit Mode"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        obj = context.active_object
        if obj and obj.type == 'GREASEPENCIL':
            bpy.ops.object.mode_set(mode='EDIT')
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Active object is not a Grease Pencil object.")
            return {'CANCELLED'}

class GoBackToHome(bpy.types.Operator):
    """Go back to Mouth Drawing Step"""
    bl_idname = "object.go_back_to_mouths"
    bl_label = "Go Back to Mouth Drawing"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.gp_face_mode = 'NONE'
        return {'FINISHED'}


##### UI Panel #####
class GPFaceRigPanel:
    """Creates a Panel in the viewport for GP Face Tools"""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GP Faces'
    
    
class GP_PT_Face_Rig_Workflow_Panel(Panel, GPFaceRigPanel):
    bl_label = "Attaboy's Grease Pencil Face Rig Workflow"
    bl_parent_idname = "VIEW3D_PT_gp_face_rig_panel"
    
    def draw(self, context):
        layout = self.layout
        obj = context.object
        settings = context.scene.grease_pencil_face_rig_settings
        scn = context.scene

        
        is_drawing = context.mode in {'PAINT_GREASE_PENCIL', 'EDIT_GREASE_PENCIL'}
        is_drawing_mouths = is_drawing and scn.gp_face_mode == 'MOUTHS'
        is_drawing_eyes = is_drawing and scn.gp_face_mode == 'EYES'
        has_setup = scn.has_setup_been_run
        has_rig = scn.rig_created

        collection = bpy.data.collections.get("Mouth Rig Control Board Objects")
        has_mouth_shapes = bool(
            collection and any(o.type == 'GREASEPENCIL' for o in collection.objects)
        )
        
        lattice = bpy.data.objects.get("GPMouthLattice")
        rig = bpy.data.objects.get("GP Mouth Rig")
        rig_settings = context.scene.target_rig_settings
        shrinkwrap_settings = context.scene.shrinkwrap_settings

        # -------------------------
        # STEP 1 — Start
        # -------------------------
        
        box = layout.box()
        row = box.row()
        row.label(text="1. Start!", icon='FILE_NEW')
        
        row = box.row()
        row.enabled = not has_setup  # grey out once setup is done
        row.operator(SetUp.bl_idname, text="Create New GP Mouth Rig", icon='FILE_NEW')

        # -------------------------
        # STEP 2 — Draw Features
        # -------------------------
        
        box = layout.box()
        row = box.row()
        row.label(text="2. Draw Features", icon='GREASEPENCIL')

        # Create Mouth Shapes button — greyed out if setup not done or currently drawing
        row = box.row()
        row.enabled = has_setup and not is_drawing
        row.operator(
            ViewCenterOriginMouths.bl_idname, 
            text="Create Mouth Shapes", 
            icon='FILE_NEW'
        )

        # -------------------------
        # STEP 3 — Drawing Controls
        # -------------------------
        
        
        
        box = layout.box()
        box.enabled = is_drawing_mouths  
        box.label(text="3. Drawing Controls", icon='BRUSH_DATA')

        box.label(text="Mouth Shape Name:")
        box.prop(settings, "mouth_shape_name", text="")
        
        box.operator(GPAddNewLayer.bl_idname, text="New Layer", icon='ADD')
        box.operator(FinishMouthShape.bl_idname, text="Finish Mouth Shape", icon='CHECKMARK')
        
        box.separator()
        box.operator(GPDoneDrawingMouth.bl_idname, text="Done Drawing", icon='EXPORT')

        # Onion skinning — only show if there are shapes to preview
        if has_mouth_shapes:
            box.separator()
            row = box.row()
            icon = 'ONIONSKIN_ON' if settings.use_onion_skinning else 'ONIONSKIN_OFF'
            row.prop(settings, "use_onion_skinning", text="Onion Preview", toggle=True, icon=icon)

            if settings.use_onion_skinning:
                col = box.column(align=True)
                col.prop(settings, "onion_preview_index", text="Shape", slider=False)
                
                gp_duplicates = [o for o in collection.objects if o.type == 'GREASEPENCIL']
                idx = settings.onion_preview_index
                if gp_duplicates and 0 <= idx < len(gp_duplicates):
                    col.label(text=f"Showing: {gp_duplicates[idx].name}", icon='GREASEPENCIL')

                row = box.row(align=True)
                op_prev = row.operator("my.onion_navigate", text="Previous", icon='TRIA_LEFT')
                op_prev.direction = -1
                op_next = row.operator("my.onion_navigate", text="Next", icon='TRIA_RIGHT')
                op_next.direction = 1

                box.prop(settings, "onion_opacity", slider=True)

        # elif is_drawing_eyes:
        #     box = layout.box()
        #     box.label(text="3. Drawing Controls", icon='BRUSH_DATA')
        #     box.label(text="Eyes coming soon!")
        #     box.operator(GoBackToHome.bl_idname, text="Go Back")

        # -------------------------
        # STEP 4 — Finalize / Create Rig
        # -------------------------
        
        box = layout.box()
        row = box.row()
        row.label(text="4. Create Rig and Finalize", icon='ARMATURE_DATA')

        row = box.row()
        row.enabled = has_setup and not is_drawing  # grey if not ready or still drawing
        row.operator(CreateRig.bl_idname, text="Create Rig", icon='ARMATURE_DATA')

        # -------------------------
        # STEP 5 — Append to existing rig
        # -------------------------
        
        box = layout.box()
        row = box.row()
        row.label(text="5. Append to Character Rig", icon='LINKED')

        col = box.column()
        col.enabled = has_rig  # grey until rig is created

        rig = find_rig(context)
        col.label(text="If you have an existing character rig, you can append the face rig to it.", icon='INFO')
        col.label(text="Select the target rig and the Attaboy Face rig below and click 'Append to Existing Rig'.", icon='INFO')
        if has_rig and rig:
            col.prop(rig_settings, "face_rig", text="Face Rig Name", icon='ARMATURE_DATA')
            col.prop(rig_settings, "target_rig", icon='ARMATURE_DATA')
            if rig_settings.target_rig:
                col.prop_search(
                    rig_settings,
                    "head_bone_name", 
                    rig_settings.target_rig.data,
                    "bones",
                    icon='BONE_DATA'
                )
                if rig_settings.head_bone_name:
                    col.operator(MY_OT_append_to_rig_permanent.bl_idname, text="Append to Existing Rig")
                else:
                    col.label(text="Select the bone that would be the head of the character from the target rig", icon='INFO')
            else:
                col.label(text="Select a character rig above", icon='INFO')
        else:
            col.label(text="Create the rig first (Step 4)", icon='INFO')

        # -------------------------
        # STEP 6 — Shrinkwrap
        # -------------------------
        
        box = layout.box()
        row = box.row()
        row.label(text="6. Bind to 3D Object (Optional)", icon='MOD_SHRINKWRAP')

        col = box.column()
        col.enabled = has_rig

        
        col.label(text="Choose shrinkwrap target mesh and lattice, then apply modifier to bind rig to the surface.", icon='INFO')
        col.prop(shrinkwrap_settings, "target_lattice")
        col.prop(shrinkwrap_settings, "target_object", icon='MESH_DATA')
        
        
        if shrinkwrap_settings.target_object and shrinkwrap_settings.target_lattice:
            col.operator(
                MY_OT_apply_shrinkwrap.bl_idname, 
                text="Apply Shrinkwrap Modifier"
            )
            if lattice and lattice.modifiers.get("Shrinkwrap"):
                col.label(text="Use 'Above Surface' to prevent clipping", icon='INFO')
            else:
                col.label(text="Shrinkwrap settings can be found in the lattice's modifier panel.", icon='INFO')
        else:
            col.label(text="Select a target mesh above", icon='INFO')              

# Registration

classes = (
    GreasePencilFaceRigSettings,
    ShrinkwrapSettings,
    TargetRigSettings,
    FinishMouthShape,
    SetUp,
    ViewCenterOriginMouths,
    ViewCenterOriginEyes,
    viewCenterOriginNose,
    GP_PT_Face_Rig_Workflow_Panel,
    GPAddNewLayer,
    CreateRig,
    MY_OT_apply_shrinkwrap,
    GPDoneDrawingMouth,
    EyeItem,
    MY_OT_set_eye_layer,
    finishEyeShape,
    GoBackToHome,
    MY_OT_onion_navigate,
    MY_OT_enter_edit_mode,
    MY_OT_append_to_rig_permanent,
    MY_OT_append_to_rig_simple,
    
)


def update_GP_tab():
    try:
        bpy.utils.unregister_class(GP_PT_Face_Rig_Workflow_Panel)
    except:
        pass
    bpy.utils.register_class(GP_PT_Face_Rig_Workflow_Panel)
    #interface_classes = (GP_PT_Face_Rig_Workflow_Panel, "")
    #for cls in interface_classes:
        #try:
            #bpy.utils.unregister_class(cls)
        #except:
            #pass
    #for cl in interface_classes:
        #bpy.utils.register_class(cl)


def register():
    
    #Register prop group!
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            
        except: 
            pass
    update_GP_tab()
    #Do we need edit/object modes for each mouth part? Eyes_edit for example
    bpy.types.Scene.grease_pencil_face_rig_settings = bpy.props.PointerProperty(type=GreasePencilFaceRigSettings)
    bpy.types.Scene.finish_mouth_count = bpy.props.IntProperty(name="Finish Mouth Count", default=0)
    bpy.types.Scene.face_layers = bpy.props.IntProperty(name="Face Layer Count", default=1)
    bpy.types.Scene.gp_active_tab = EnumProperty(
        items=(('CREATE', 'Create', 'Create Tab'), ('EDIT', 'Edit', ' Edit Tab'), ('TOOLS', 'Misc', 'Misc Tab')), options={'HIDDEN'})
    bpy.types.Scene.gp_face_mode = EnumProperty(
        items=(('MOUTHS', 'Mouths', 'Mouths Mode'), ('EYES', 'Eyes', 'Eyes Mode'), ('NOSE', 'Nose', 'Nose Mode'), ('NONE', 'None', 'default')), options={'HIDDEN'})
    bpy.types.Scene.number_of_eyes = bpy.props.IntProperty(name="Number of Eyes", default=2, min=1, max = 10, description="Number of eyes to generate")
    bpy.types.Scene.has_setup_been_run = bpy.props.BoolProperty(name="Has SetUp Been Run", default=False)
    bpy.types.Scene.shrinkwrap_settings = bpy.props.PointerProperty(type=ShrinkwrapSettings)
    bpy.app.driver_namespace['get_bone_distance'] = get_bone_distance
    bpy.types.Scene.eye_collection = bpy.props.CollectionProperty(type=EyeItem)
    bpy.types.Scene.active_eye_index = bpy.props.IntProperty(default=0)
    bpy.types.Scene.use_onion_skinning = bpy.props.BoolProperty(name="Enable Onion Skinning", default=False)
    bpy.types.Scene.target_rig_settings = bpy.props.PointerProperty(type = TargetRigSettings)
    bpy.types.Scene.rig_created = bpy.props.BoolProperty(name="Rig Created", default=False)
    
def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.finish_mouth_count
    del bpy.types.Scene.face_layers
    del bpy.types.Scene.grease_pencil_face_rig_settings
    del bpy.types.Scene.gp_active_tab
    if 'get_bone_distance' in bpy.app.driver_namespace:
        del bpy.app.driver_namespace['get_bone_distance']
    del bpy.types.Scene.has_setup_been_run
    del bpy.types.Scene.shrinkwrap_settings
    del bpy.types.Scene.target_rig_settings
    del bpy.types.Scene.use_onion_skinning
    del bpy.types.Scene.number_of_eyes
    del bpy.types.Scene.rig_created

if __name__ == "__main__":
    register()