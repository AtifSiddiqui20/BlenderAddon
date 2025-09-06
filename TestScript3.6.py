bl_info = {
    "name": "View and Movement Tools",
    "author": "Attaboy!",
    "version": (0, 0, 1),
    "blender": (3, 6, 0),
    "category": "Grease Pencil",
    "location": "View 3D > Tool Shelf > GP Face tool",
    "description": "Create and edit 2d faces with Grease Pencil",
}

# Current Issues for mouths: 
# UI shenaningans
# Correct Scale needed - Hopefully solved

# Current Issues for Eyes
 #Not yet implemented 

#missing features for mouths: 
# The created bones for each shape should be able to move the gp shapes-DONE
# they correspond to, so every mouth shape should be moveable
# via the hidden bones, that means they are shinkrwrapped to the plane
# show hidden bones button? 
# Bone for mouth control/canvas
# Widgets 

# and the Gp objects need to move too 
# Scale thickness needs to be ON for all grease pencil objects X
# Use Lights Button
# Hooks for lattice setup? Lattice needs vertex groups


# Adding lablels to controla board rig (bones that take the shape
#of text. Missing eye, eyebrows, and nose creation. Missing lattice creation and bone parenting
#appending to rigs, making the interface use drivers for x and y movement, allowing it to 
# snap to shapes rather than freely move about (only for mouth and eye shapes)
# Eyebrow Sliders/controls 
# Lattice creation with bone hooks for every part
# Add Delete Rig button for my collection

#Tips/things to remember: 
# Always use transform space
# It is the Z location, not Y locaiton.
# apply scaling and rotation to custom bone shape meshes

import bpy
import bmesh
import os
import math
import re
from mathutils import Vector


def get_bone_distance(armature, bone1_name, bone2_name):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    armature_eval = armature.evaluated_get(depsgraph)
    
    bone1 = armature_eval.pose.bones[bone1_name]
    bone2 = armature_eval.pose.bones[bone2_name]
    
    world_pos1 = armature.matrix_world @ bone1.matrix @ Vector((0, 0, 0))
    world_pos2 = armature.matrix_world @ bone2.matrix @ Vector((0, 0, 0))
    
    distance = (world_pos1 - world_pos2).length
    return distance


class GreasePencilFaceRigSettings(bpy.types.PropertyGroup):
    mouth_shape_name: bpy.props.StringProperty(
        name="Mouth Shape Name",
        description="Enter a name for the mouth shape",
        default="",
        maxlen=25,
    )
    Eye_shape_name: bpy.props.StringProperty(
        name="Eye Shape Name",
        description="Enter a name for the eye shape",
        default="",
        maxlen=25,
    )
    
    
    
    
    

# Operator to center view on the world origin
class ViewCenterOriginMouths(bpy.types.Operator):
    "Center the view on the world origin, add a plane, create a Grease Pencil object with a correctly configured material, and enter draw mode"""
    bl_idname = "view3d.center_origin"
    bl_label = "Create Grease Pencil!"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        bpy.ops.view3d.view_axis(type='FRONT')

        # Collection handling
        collection_name = "Temp Drawing Collection"
        if collection_name not in bpy.data.collections:
            collection = bpy.data.collections.new(collection_name)
            context.scene.collection.children.link(collection)
        else:
            collection = bpy.data.collections[collection_name]

        # Plane creation and setup
        plane_name = "Target Drawing Plane"
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

        # Grease Pencil object and material setup
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
        bpy.ops.object.mode_set(mode = 'EDIT_GPENCIL')
        bpy.context.scene.tool_settings.gpencil_sculpt.use_scale_thickness = True
        bpy.ops.object.mode_set(mode='PAINT_GPENCIL')
        new_layer = gp_obj.data.layers.new(name="New GP Layer", set_active=True)
        new_layer.info = "New GP Layer"  # Optional: set a name for the layer
        new_layer.frames.new(frame_number=0)  # Ensure there's a frame to draw on

        # Material setup
        if "Default Material" in bpy.data.materials.keys():
            gp_mat = bpy.data.materials["Default Material"]
        else:
            gp_mat = bpy.data.materials.new("Default Matieral")

        if not gp_mat.is_grease_pencil:
            bpy.data.materials.create_gpencil_data(gp_mat)
            gp_mat.grease_pencil.color = (0, 0, 0, 1)

            gp_data.materials.append(gp_mat)
            bpy.ops.gpencil.draw(wait_for_input=False)

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
                        override = {'area': area, 'region': region, 'space_data': area.spaces.active,
                                    'region_3d': area.spaces.active.region_3d}
                        bpy.ops.view3d.view_selected(override)
                        obj.hide_select = True
                        break

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
        return gp_obj.data.materials[0]


class GPAddNewLayer(bpy.types.Operator):
    """Add a new layer to the active Grease Pencil object"""
    bl_idname = "gpencil.add_new_layer"
    bl_label = "New Layer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        gp_obj = context.active_object
        if gp_obj and gp_obj.type == 'GPENCIL':
            new_layer = gp_obj.data.layers.new(name="New GP Layer", set_active=True)
            new_layer.info = "New GP Layer"  # Optional: set a name for the layer
            new_layer.frames.new(frame_number=0)  # Ensure there's a frame to draw on
            face_layer_count = context.scene.face_layers
            face_layer_count += 1
            self.report({'INFO'}, "New layer added and activated for drawing.")
            return {'FINISHED'}
        self.report({'ERROR'}, "Active object is not a Grease Pencil object.")
        return {'CANCELLED'}


class FinishEyeShape(bpy.types.Operator):
    """Duplicate Eye drawings, scale, move them to correct locations on control board"""
    bl_idname = "gpencil.finish_eye_shapes"
    bl_label = "Finish Eye Shape"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        return


class FinishMouthShape(bpy.types.Operator):
    """Duplicate the GP object, scale it, move it, and prepare the original for new drawing"""
    bl_idname = "gpencil.finish_mouth_shape"
    bl_label = "Finish Mouth Shape"
    bl_options = {'REGISTER', 'UNDO'}

    def is_layer_empty(self, layer):
        """Check if a Grease Pencil layer is empty"""
        for frame in layer.frames:
            if frame.strokes:
                return False
        return True

    def execute(self, context):
        # Get the name for the mouth shape from the property group
        mouth_name = bpy.context.scene.grease_pencil_face_rig_settings.mouth_shape_name
        # print(mouth_name)

        # Check if the mouth shape name is provided
        if not mouth_name:
            self.report({'WARNING'}, "You should enter a name for the mouth shape")
            return {'CANCELLED'}

        # Get the active object
        gp_obj = context.active_object
        if gp_obj and gp_obj.type == 'GPENCIL':

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
                    layer.info = mouth_name
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
        ## Currently Assigns Correctly, but not armatured (had to turn on deform for mouth shape bones)
        ## make sure to make the letters move too. Might have to redo it with constraints instead
        # to move in Object modfe rather than edit mode
        # also the extra layers arent being deleted
            if gp_duplicate and gp_duplicate.type == 'GPENCIL':
            # Create or get the vertex group
                vgroup_name = mouth_name + " Shape Bone"
                if vgroup_name not in gp_duplicate.vertex_groups:
                    gp_duplicate.vertex_groups.new(name=vgroup_name)
                # Enter edit mode
                bpy.ops.object.mode_set(mode='EDIT_GPENCIL')
#                # Reveal all existing layers in the original GP object
#                for layer in gp_duplicate.data.layers:
#                    layer.hide = False
                # Select all strokes
                bpy.ops.gpencil.select_all(action='SELECT')
                # Assign selected vertices to the vertex group
                for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                override = {'area': area, 'region': region, 'edit_object': bpy.context.edit_object}
                                bpy.ops.gpencil.vertex_group_assign(override)
                                break
                bpy.ops.object.mode_set(mode='OBJECT')
                self.report({'INFO'}, "Vertices added to mouth controller vertex group.")

            # Scale the duplicate
            gp_duplicate.scale *= 2.5
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
            base_scale = 0.1
            text_length = len(text_obj.data.body)

            # Adjust the scale inversely proportional to the length of the text
            scale_factor = base_scale / (text_length * 0.2)
            if text_length > 6:
                text_obj.scale = (scale_factor, scale_factor, scale_factor)
            else:
                text_obj.scale = (.1, .1, .1)
            
            # Link the text object & Duplicate to the new collection
            new_collection.objects.link(gp_duplicate)
            new_collection.objects.link(text_obj)
            parent_collection.objects.unlink(gp_duplicate)
            bpy.context.scene.collection.objects.unlink(text_obj)

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
            new_layer.info = "New Mouth Layer"  # Optional: set a name for the layer
            new_layer.frames.new(frame_number=0)  # Ensure there's a frame to draw on

            # Enter draw mode on the original GP object
            bpy.ops.object.mode_set(mode='PAINT_GPENCIL')

            # Clear the mouth_shape_name property
            context.scene.grease_pencil_face_rig_settings.mouth_shape_name = ""

            self.report({'INFO'}, "Mouth shape finished. Ready for new drawing.")
            return {'FINISHED'}
        self.report({'ERROR'}, "Active object is not a Grease Pencil object.")
        return {'CANCELLED'}



class GPDoneDrawingMouth(bpy.types.Operator):
    """Exit draw mode and arrange duplicated GP objects"""
    bl_idname = "gpencil.done_drawing"
    bl_label = "Done"
    bl_options = {'REGISTER', 'UNDO'}
    
    def remove_object_by_name(self, name):
        if name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
        

    def execute(self, context):
        
        #Need to check for drawings currently not saved with name
        # Get the active object
#        gp_obj = context.active_object
#        if gp_obj and gp_obj.type == 'GPENCIL':
#            active_layer = gp_obj.data.layers.active
#            if active_layer
#        
#        mouth_name = bpy.context.scene.grease_pencil_face_rig_settings.mouth_shape_name
#        if mouth_name and 
        
         
        # Ensure there are no name conflicts
        self.remove_object_by_name("Mouth Shape Control Selector")
        context.active_object.select_set(True)
        gp_obj = context.active_object
        if gp_obj and gp_obj.type == 'GPENCIL':
            # Create or get the vertex group
            vgroup_name = "GP Mouth Bone"
            if vgroup_name not in gp_obj.vertex_groups:
                gp_obj.vertex_groups.new(name=vgroup_name)

            # Enter edit mode
            bpy.ops.object.mode_set(mode='EDIT_GPENCIL')

            # Reveal all existing layers in the original GP object
            for layer in gp_obj.data.layers:
                layer.hide = False

            # Select all strokes
            bpy.ops.gpencil.select_all(action='SELECT')

            # Assign selected vertices to the vertex group
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            override = {'area': area, 'region': region, 'edit_object': bpy.context.edit_object}
                            bpy.ops.gpencil.vertex_group_assign(override)
                            break
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, "Vertices added to mouth controller vertex group.")

        # Arrange the duplicated objects in the "Duplicated GP Objects" collection
        collection_name = "Mouth Rig Control Board Objects"
        collection = bpy.data.collections.get(collection_name)

        if collection is not None:
            # Define the spacing between objects
            spacing_x = .5
            spacing_z = .5
            items_per_row = 4

            # Initialize the position variables
            x = 2.0
            z = 2.25
            plsize = 0  # initialize the plane size

            # Iterate through the objects in the collection
            gp_object_count = 0  # Counter for Grease Pencil objects
            for obj in collection.objects:
                obj.hide_viewport = False
                # Set the object's location if they are GP objects
                if obj.type == 'GPENCIL':
                    obj.location.x = x
                    obj.location.z = z
                    gp_object_count += 1
                    
                    # Update the x position for the next object
                    x += spacing_x

                    # Check if we need to move to the next row
                    if (gp_object_count % items_per_row == 0):
                        x = 2.0  # Reset x position for the new row
                        z -= spacing_z  # Move to the next row
                        plsize += 1  # Increment the plane's z scaling

            # Create Another Plane and resize it to the size of the mouths
            bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=True, location=(2, 0, 2), rotation=(1.5708, 0, 0))
            plane = context.active_object
            plane.name = "Mouths Control Board Plane"
            #plane.transform_apply(location = False, scale = True, rotation = False)
            if plsize != 0:
                if plsize != 1:
                    plane.scale = (2, plsize *.5, plsize / 1.9)
                else: 
                    plane.scale = (2, plsize, plsize/1.9)
            else:
                plane.scale = (2, .403, .403)
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
                            override = {'area': area, 'region': region, 'edit_object': plane}
                            bpy.ops.view3d.snap_cursor_to_selected(override)
                            break
                    else:
                        continue
                    break

            # Return to object mode and set the origin to the cursor
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
            bpy.context.scene.cursor.location = (0, 0, 0)  # Reset the cursor location

            plane.location.x = 1.8
            plane.location.z = 2.4
            

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
                bpy.ops.mesh.primitive_circle_add(fill_type='NGON', vertices=16, radius=0.1, location=(
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
#                    if obj.type == 'GPENCIL': 
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
            

            # Return to Gpencil object
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
            
            # Assign lattice Vertices to Bones in rig

            # Add a lattice modifier to the GP object
            bpy.ops.object.select_all(action='DESELECT')
            gp_obj.select_set(True)
            context.view_layer.objects.active = gp_obj
            mod = bpy.ops.object.gpencil_modifier_add(type='GP_LATTICE')
            bpy.context.object.grease_pencil_modifiers["Lattice"].object = bpy.data.objects["GPMouthLattice"]
            collection.objects.link(lattice)
            context.collection.objects.unlink(lattice)

            self.report({'INFO'},
                        f"Arranged {len(collection.objects)} objects in {(len(collection.objects) + items_per_row - 1) // items_per_row} rows.")
        else:
            self.report({'ERROR'}, f"Collection '{collection_name}' not found.")

        return {'FINISHED'}


class CreateRig(bpy.types.Operator):
    """Create a rig with two bones: one named after the vertex group and the other named root"""
    bl_idname = "object.create_rig"
    bl_label = "Create Rig"
    bl_options = {'REGISTER', 'UNDO'}


    def execute(self, context):
############################### Widget Creation/Import and Organization ####################




############################### Face Control Board Creation ################################        
        
        
        
        
################################ Mouth Rig Creation ########################################
        # Get the active object
        gp_obj = context.active_object
        if gp_obj and gp_obj.type == 'GPENCIL':
            vgroup_name = "GP Mouth Bone"
            if vgroup_name not in gp_obj.vertex_groups:
                self.report({'ERROR'}, f"Vertex group '{vgroup_name}' not found.")
                return {'CANCELLED'}
            
        # Retrieve control board and puck locations
        collection_name = "Mouth Rig Control Board Objects"
        collection = bpy.data.collections.get(collection_name)
            


        # Create a new armature object
        bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
        armature = context.object
        armature.name = "GP_Rig"
        bpy.ops.object.mode_set(mode='EDIT')

        # Access the armature's edit bones
        bones = armature.data.edit_bones

        # Create the root bone, it's slightly offset
        # from the mouth to be in the center of the head it'll join with
        root_bone = bones[0]
        root_bone.name = "GP Face Rig Root"
        root_bone.head = (0, 1, 0)
        root_bone.tail = (0, 1, 0.5)

        # Create the named bone and place it in middle of Lattice
        named_bone = bones.new(vgroup_name)
        named_bone.head = (0, 0, -0.05)
        named_bone.tail = (0, 0, 0.05)
        named_bone.parent = root_bone
        named_bone.use_connect = False
        
        # Retrieve control board and puck locations
        collection_name = "Mouth Rig Control Board Objects"
        collection = bpy.data.collections.get(collection_name)

        if collection is None:
            self.report({'ERROR'}, f"Collection '{collection_name}' not found.")
            return {'CANCELLED'}

        control_board = None
        puck = None
        for obj in collection.objects:
            if obj.name == "Mouths Control Board Plane":
                control_board = obj
                obj.hide_viewport = True
            elif obj.name == "Mouth Shape Control Selector":
                puck = obj
                puck.hide_viewport =True
            
        if not control_board or not puck:
            self.report({'ERROR'}, "Control board or Selector not found in the collection.")
            return {'CANCELLED'}
        
        # Create the control board bone
        control_board_bone = bones.new("control_board")
        control_board_bone.head = control_board.location
        control_board_bone.tail = (control_board.location.x, control_board.location.y, control_board.location.z + control_board.scale.z)
        control_board_bone.parent = root_bone
        control_board_bone.use_connect = False
        control_board_bone.use_deform = False
        control_board_bone.show_wire = True
        
        # Create the puck control bone
        mouth_puck_control_bone = bones.new("mouth_puck_control")
        mouth_puck_control_bone.head = puck.location
        mouth_puck_control_bone.tail = (puck.location.x, puck.location.y, puck.location.z + 0.2)
        mouth_puck_control_bone.parent = control_board_bone
        mouth_puck_control_bone.use_connect = False
        
        #Create Bones for each GP object in the other collection and set them to hide
        bone_names = []
        
        for obj in collection.objects[:] :
            if obj.type == 'GPENCIL':
                bone_name = obj.name
                print(f"Creating bone for: {bone_name}") 
                mouth_shape_bone = bones.new(bone_name + " Shape Bone")
                mouth_shape_bone.head = obj.location
                mouth_shape_bone.tail = (obj.location.x, obj.location.y, obj.location.z + 0.2)
                mouth_shape_bone.parent = control_board_bone
                mouth_shape_bone.use_connect = False
                mouth_shape_bone.use_deform = True
                mouth_shape_bone.hide = True
                bone_names.append(mouth_shape_bone.name)
                # Add constraints to duplicated GP Mouths to the rig's bones of the same name
                childof_dup_gp_face = obj.constraints.new('CHILD_OF')
                childof_dup_gp_face.target = armature
                childof_dup_gp_face.subtarget = mouth_shape_bone.name
                bpy.context.view_layer.update()
                bpy.ops.object.mode_set(mode='OBJECT')
                bpy.context.view_layer.update()
                # Select the object before applying the inverse
                bpy.context.view_layer.objects.active = obj  # Ensure obj is active

                # Switch to Object Mode (required for setting inverse)
                bpy.ops.object.mode_set(mode='OBJECT')

                # Apply the inverse
                bpy.ops.constraint.childof_set_inverse(constraint=childof_dup_gp_face.name, owner='OBJECT')  

                # Ensure Blender updates again
                bpy.context.view_layer.update()
                obj.update_tag(refresh={'OBJECT'})

                

                print(f"Created bone: {mouth_shape_bone.name} with object constraint")
                  
        # Switch back to the armature
        bpy.context.view_layer.objects.active = armature  
        # Switch to pose mode to set custom shapes & visbility rules
        bpy.ops.object.mode_set(mode='POSE')
        # Access the pose bones
        pose_bones = armature.pose.bones
        # Set custom shapes (ensure you have created custom bone shapes named 'ControlBoardShape' and 'PuckShape')
        if 'Mouths Control Board Plane' in bpy.data.objects:
            control_board_bone_obj = pose_bones["control_board"]
            control_board_bone_obj.custom_shape = bpy.data.objects['Mouths Control Board Plane']
            
            control_board_bone_obj.use_custom_shape_bone_size = False
            for child_bone in control_board_bone_obj.children:
                child_bone.bone.hide = True

        if 'Mouth Shape Control Selector' in bpy.data.objects:
            mouth_puck_control_bone_obj = pose_bones["mouth_puck_control"]
            mouth_puck_control_bone_obj.custom_shape = bpy.data.objects['Mouth Shape Control Selector']
            mouth_puck_control_bone_obj.use_custom_shape_bone_size = False
            mouth_puck_control_bone_obj.bone.hide = False
        
        # Add shrinkwrap constraint to the puck bone
        shrinkwrap = mouth_puck_control_bone_obj.constraints.new('SHRINKWRAP')
        shrinkwrap.target = control_board
        shrinkwrap.wrap_mode = 'ON_SURFACE'
        # shrinkwrap.use_keep_above_surface = True

        # Switch back to object mode
        bpy.ops.object.mode_set(mode='OBJECT')

        # Parent the GP object to the armature with weights previously defined
        gp_obj.select_set(True)
        armature.select_set(True)
        context.view_layer.objects.active = armature
        bpy.ops.object.parent_set(type='ARMATURE')
        

        # Set up drivers for layer visibility using bones
        
        for layer in gp_obj.data.layers:
            for bone_name in bone_names:
                layer_pattern = re.compile(f"^{bone_name.replace(' Shape Bone', '')}(\.\d+)?$")
                if layer_pattern.match(layer.info):
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
        control_board_bone_obj = armature.pose.bones["control_board"]
        mouth_puck_control_bone_obj = armature.pose.bones["mouth_puck_control"]
        
        childof_puck = puck.constraints.new('CHILD_OF')
        childof_puck.target = armature
        childof_puck.subtarget = "mouth_puck_control"
        childof_control_board = control_board.constraints.new('CHILD_OF')
        childof_control_board.target = armature
        childof_control_board.subtarget = "control_board"

        # Add the armature to the same collection as the Grease Pencil object
        collection = gp_obj.users_collection[0]
        if armature.users_collection:
            for coll in armature.users_collection:
                coll.objects.unlink(armature)
            collection.objects.link(armature)
            
        # Find the lattice object and add a CHILD_OF constraint to it
        lattice = bpy.data.objects.get("GPMouthLattice")
        if lattice:
            lattice_constraint = lattice.constraints.new(type =  'CHILD_OF')
            lattice_constraint.target = bpy.data.objects["GP_Rig"]
            lattice_constraint.subtarget = "GP Mouth Bone"
        # Create bones for lattice and assign vertex groups to vertices to mouth bone - set to linear 
        
        
        
        
        # Add bones to control hooks 
            # lattice_constraint.childof_set_inverse(constraint="Child Of", owner='OBJECT')

        # Create Mouth Face Rig Control Panel

            self.report({'INFO'}, "Rig created with two bones.")
            return {'FINISHED'}
        self.report({'ERROR'}, "Active object is not a Grease Pencil object.")
        return {'CANCELLED'}


# Panel to hold the buttons
class ToolsPanel(bpy.types.Panel):
    """Creates a Panel in the viewport for GP Face Tools"""
    bl_label = "Grease Pencil Face Tools"
    bl_idname = "VIEW3D_PT_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GP Face Tools'

    def draw(self, context):
        layout = self.layout
        obj = context.object

        # Step 1: Create or Edit Rig
        if context.mode not in {'PAINT_GPENCIL', 'EDIT_GPENCIL'}:
            col = layout.column(align=True)
        
            col.label(text="1. Start")
            col.alert = True
            col.operator(ViewCenterOriginMouths.bl_idname, text="Create a new GP Face Rig", icon='FILE_NEW')
            col.alert = False
            col.operator(ViewCenterOriginMouths.bl_idname, text="Edit an existing Rig", icon = 'EDITMODE_HLT')

        # Step 2: Draw Facial Features by each feature
        col = layout.column(align=True)
        col.label(text="2. Draw Features")
        col.operator("gpencil.draw_eyes", text="Draw Eyes")
        if obj and obj.type == 'GPENCIL' and context.mode in {'PAINT_GPENCIL', 'EDIT_GPENCIL'}:
            col.operator(GPAddNewLayer.bl_idname, text="New Layer")
            row = col.row()
            row.prop(context.scene.grease_pencil_face_rig_settings, "mouth_shape_name")
            col.operator(FinishMouthShape.bl_idname, text="Finish Mouth Shape")
            col.operator(GPDoneDrawingMouth.bl_idname, text="Done")
        col.operator("gpencil.draw_mouth", text="Draw Mouth")
#        if obj and obj.type == 'GPENCIL' and context.mode in {'PAINT_GPENCIL', 'EDIT_GPENCIL'}:
#            col.operator(GPAddNewLayer.bl_idname, text="New Layer")
#            row = col.row()
#            row.prop(context.scene.grease_pencil_face_rig_settings, "mouth_shape_name")
#            col.operator(FinishMouthShape.bl_idname, text="Finish Mouth Shape")
#            col.operator(GPDoneDrawingMouth.bl_idname, text="Done")
#        col.operator("gpencil.draw_nose", text="Draw Nose")
#        if obj and obj.type == 'GPENCIL' and context.mode in {'PAINT_GPENCIL', 'EDIT_GPENCIL'}:
#            col.operator(GPAddNewLayer.bl_idname, text="New Layer")
#            row = col.row()
#            row.prop(context.scene.grease_pencil_face_rig_settings, "mouth_shape_name")
#            col.operator(FinishMouthShape.bl_idname, text="Finish Mouth Shape")
#            col.operator(GPDoneDrawingMouth.bl_idname, text="Done")

#        # Step 3: Drawing, Editing, Sculpting Tools
#        col = layout.column(align=True)
#        col.label(text="3. Tools")
#        if obj and obj.type == 'GPENCIL' and context.mode in {'PAINT_GPENCIL', 'EDIT_GPENCIL'}:
#            col.operator(GPAddNewLayer.bl_idname, text="New Layer")
#            row = col.row()
#            row.prop(context.scene.grease_pencil_face_rig_settings, "mouth_shape_name")
#            col.operator(FinishMouthShape.bl_idname, text="Finish Mouth Shape")
#            col.operator(GPDoneDrawingMouth.bl_idname, text="Done")

        # Step 4: Create Rig
        col = layout.column(align=True)
        col.label(text="4. Finalize")
        col.operator(CreateRig.bl_idname, text="Create Rig")



#class ToolsPanel(bpy.types.Panel):
#    """Creates a Panel in the viewport for GP Face Tools"""
#    bl_label = "Grease Pencil Face Tools"
#    bl_idname = "VIEW3D_PT_tools"
#    bl_space_type = 'VIEW_3D'
#    bl_region_type = 'UI'
#    bl_category = 'GP Face tools'

#    def draw(self, context):
#        name = context.scene.grease_pencil_face_rig_settings
#        layout = self.layout
#        obj = context.object

#        if obj is None or obj.type != 'GPENCIL' or context.mode not in {'PAINT_GPENCIL', 'EDIT_GPENCIL'}:
#            layout.operator(ViewCenterOriginMouths.bl_idname, text="Create Grease Pencil")

#        if obj and obj.type == 'GPENCIL' and context.mode in {'PAINT_GPENCIL', 'EDIT_GPENCIL'}:
#            layout.operator(GPAddNewLayer.bl_idname, text="New Layer")
#            # layout.operator(GPAddVerticesToGroup.bl_idname, text="Add Vertices to Group")
#            # Add text field and Finish Mouth Shape operator
#            row = layout.row()
#            row.prop(name, "mouth_shape_name")
#            layout.operator(FinishMouthShape.bl_idname, text="Finish Mouth Shape")

#            layout.operator(GPDoneDrawingMouth.bl_idname, text="Done")
#        if obj is None or obj.type != 'GPENCIL' or context.mode not in {'PAINT_GPENCIL', 'EDIT_GPENCIL'}:
#            layout.operator(CreateRig.bl_idname, text="Create Rig")


# Registration

classes = (
    GreasePencilFaceRigSettings,
    FinishMouthShape,
    ViewCenterOriginMouths,
    ToolsPanel,
    GPAddNewLayer,
    CreateRig,
    GPDoneDrawingMouth
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.finish_mouth_count = bpy.props.IntProperty(name="Finish Mouth Count", default=0)
    bpy.types.Scene.face_layers = bpy.props.IntProperty(name="Face Layer Count", default=1)
    bpy.types.Scene.grease_pencil_face_rig_settings = bpy.props.PointerProperty(type=GreasePencilFaceRigSettings)
    bpy.app.driver_namespace['get_bone_distance'] = get_bone_distance


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.finish_mouth_count
    del bpy.types.Scene.face_layers
    del bpy.types.Scene.grease_pencil_face_rig_settings
    if 'get_bone_distance' in bpy.app.driver_namespace:
        del bpy.app.driver_namespace['get_bone_distance']


if __name__ == "__main__":
    register()

# Retired Methods
# class GPAddVerticesToGroup(bpy.types.Operator):
#     """Add all vertices of the active Grease Pencil object to a vertex group with weight 1"""
#     bl_idname = "gpencil.add_vertices_to_group"
#     bl_label = "Add Vertices to Group"
#     bl_options = {'REGISTER', 'UNDO'}
#
#     def execute(self, context):
#         gp_obj = context.active_object
#         if gp_obj and gp_obj.type == 'GPENCIL':
#             # Create or get the vertex group
#             vgroup_name = "GP Vertices"
#             if vgroup_name not in gp_obj.vertex_groups:
#                 gp_obj.vertex_groups.new(name=vgroup_name)
#
#             # Enter edit mode
#             bpy.ops.object.mode_set(mode='EDIT_GPENCIL')
#
#             # Select all strokes
#             bpy.ops.gpencil.select_all(action='SELECT')
#
#             # Assign selected vertices to the vertex group
#             for area in bpy.context.screen.areas:
#                 if area.type == 'VIEW_3D':
#                     for region in area.regions:
#                         if region.type == 'WINDOW':
#                             override = {'area': area, 'region': region, 'edit_object': bpy.context.edit_object}
#                             bpy.ops.gpencil.vertex_group_assign(override)
#                             break
#
#             # Return to paint mode
#             bpy.ops.object.mode_set(mode='PAINT_GPENCIL')
#
#             self.report({'INFO'}, "Vertices added to vertex group.")
#             return {'FINISHED'}
#         self.report({'ERROR'}, "Active object is not a Grease Pencil object.")
#         return {'CANCELLED'}



# retired code
 
#             # Set up drivers for layer visibility using bones
#            for layer in gp_obj.data.layers:
#                for bone_name in bone_names:
#                    if layer.info.startswith(bone_name.replace(" Shape Bone", "")):
#                        driver = layer.driver_add("hide").driver
#                        driver.type = 'SCRIPTED'
#                        var = driver.variables.new()
#                        var.name = "distance"
#                        var.type = 'LOC_DIFF'
#                        var.targets[0].id = armature
#                        var.targets[0].bone_target = "mouth_puck_control"
#                        var.targets[0].transform_type = 'LOC_X'
#                        var.targets[0].transform_space = 'TRANSFORM_SPACE'
#                        var.targets[1].id = armature
#                        var.targets[1].bone_target = bone_name
#                        var.targets[1].transform_type = 'LOC_X'
#                        var.targets[1].transform_space = 'TRANSFORM_SPACE'
#                        driver.expression = "distance > 0.1"

            
            
            # Set up drivers for layer visibility - using bones instead of the planes
            
#            for layer in gp_obj.data.layers:
#                if layer.info.startswith(""):
#                    layer_index = int(layer.info.split(" ")[-1])
#                    target_obj = collection.objects.get(f"Mouth Shape {layer_index}")
#                    if target_obj:
#                        driver = layer.driver_add("hide").driver
#                        driver.type = 'SCRIPTED'
#                        var = driver.variables.new()
#                        var.name = "distance"
#                        var.targets[0].id = armature
#                        var.targets[0].bone_target = "mouth_puck_control"
#                        var.targets[0].transform_type = 'DISTANCE'
#                        var.targets[0].transform_space = 'LOCAL_SPACE'
#                        var.targets[1].id = target_obj
#                        var.targets[1].transform_type = 'LOC_X'
#                        var.targets[1].transform_space = 'LOCAL_SPACE'
#                        driver.expression = "distance < 0.1"
#            
#            # Add drivers to control layer visibility
#            for dup_index, dup_obj in enumerate(collection.objects):
#                if dup_obj.type == 'GPENCIL':
#                    for layer in gp_obj.data.layers:
#                        if layer.info.startswith(dup_obj.name): # leads to issue where same name start causes double drivers to be added
#                            driver = layer.driver_add("hide").driver
#                            driver.type = 'SCRIPTED'
#                            # set the type first (default is 'SINGLE_PROP')
#                            var = driver.variables.new()
#                            var.type = 'LOC_DIFF'
#                            var.name = 'distance'
#                            var.targets[0].id = armature
#                            var.targets[0].bone_target = "mouth_puck_control"
#                            # var.targets[0].data_path = 'location'
#                            var.targets[0].transform_space = 'TRANSFORM_SPACE'
#                            var.targets[1].id = 
#                            # var.targets[1].data_path = 'location'
#                            var.targets[1].transform_space = 'TRANSFORM_SPACE'
#                            driver.expression = "1 - (3.02 > distance > 3)"



            # Link the duplicated object to the new collection
            #new_collection.objects.link(gp_duplicate)
            #parent_collection.objects.unlink(gp_duplicate)
            # context.collection.objects.unlink(gp_duplicate)
            
            
            #            # Set up drivers for layer visibility using bones
#            for layer in gp_obj.data.layers:
#                # layer.hide = True
#                empty_name = bone_name.replace(" Shape Bone", " empty")
#                if layer.info.startswith(bone_name.replace(" Shape Bone", "")):
#                    driver = layer.driver_add("hide").driver
#                    driver.type = 'SCRIPTED'
#            
#                    var = driver.variables.new()
#                    var.name = "distance"
#                    var.type = 'LOC_DIFF'
#            
#                    var.targets[0].id = armature
#                    var.targets[0].bone_target = "mouth_puck_control"
#                    var.targets[0].transform_space = 'TRANSFORM_SPACE'
#                    var.targets[1].id = bpy.data.objects[empty_name]
#                    var.targets[1].transform_space = 'TRANSFORM_SPACE'
#            
#                    driver.expression = "distance > 0.1"
                        
#                        drivers = gp_obj.animation_data.drivers
#                        cdriver = drivers[0]
#                        cdriver.modifiers.remove(cdriver.modifiers[0])
#                        
#                         # Access the F-Curve
#                        fcurve = gp_obj.animation_data.drivers.find("hide")
#    
#    # Ensure the F-Curve exists
#                        if fcurve:
#                            # Insert keyframes at frame 1 and 100
#                            fcurve.keyframe_points.insert(frame=1, value=0.0)
#                            fcurve.keyframe_points.insert(frame=100, value=1.0)
#                            
#                            # Optionally, you can set interpolation type (e.g., 'LINEAR', 'CONSTANT', etc.)
#                            for key in fcurve.keyframe_points:
#                                key.interpolation = 'LINEAR'


#        for layer in gp_obj.data.layers:
#            for bone_name in bone_names:
#                if layer.info.startswith(bone_name.replace(" Shape Bone", "")):
#                    bone2 = layer.info 
#                    driver = layer.driver_add("hide").driver
#                    driver.type = 'SCRIPTED'
#                    
#                    var1 = driver.variables.new()
#                    var1.name = "bone1" #+ bone2
#                    var1.type = 'TRANSFORMS'
#                    var1.targets[0].id = armature
#                    var1.targets[0].bone_target = "mouth_puck_control"
#                    var1.targets[0].transform_type = 'LOC_X'
#                    var1.targets[0].transform_space = 'TRANSFORM_SPACE'
#                    
#                    var2 = driver.variables.new()
#                    var2.name = "bone2"
#                    var2.type = 'TRANSFORMS'
#                    var2.targets[0].id = armature
#                    var2.targets[0].bone_target = bone_name
#                    var2.targets[0].transform_type = 'LOC_X'
#                    var2.targets[0].transform_space = 'TRANSFORM_SPACE'
#                    
#                    driver.expression = "(abs(bone1 - bone2) >  0.1)"
                    
            
            
#            for obj in collection.objects:
#                if obj.type == 'GPENCIL':
#                    bone_name = obj.name 
#                    mouth_shape_bone = bones.new(bone_name + " Shape Bone")
#                    mouth_shape_bone.head = obj.location
#                    mouth_shape_bone.tail = (obj.location.x, obj.location.y, obj.location.z + 0.2)
#                    mouth_shape_bone.parent = control_board_bone
#                    mouth_shape_bone.use_connect = False
#                    mouth_shape_bone.use_deform = False
            
            #        for obj in collection.objects:
#            if obj.type == 'GPENCIL':
#                bpy.ops.object.empty_add(type='PLAIN_AXES', location=mouth_shape_bone.head)
#                empty = bpy.context.object
#                empty.name = bone_name + " empty"
#                # Parent the empty to the bone
#                bpy.context.view_layer.objects.active = armature
#                bpy.ops.object.mode_set(mode='POSE')
#                bone_pose = armature.pose.bones[mouth_shape_bone.name]
#                empty.parent = armature
#                empty.parent_type = 'BONE'
#                empty.parent_bone = bone_pose.name
#                bpy.ops.object.mode_set(mode='OBJECT')


#            # Add drivers to control layer visibility
#            for dup_index, dup_obj in enumerate(collection.objects):
#                if dup_obj.type == 'GPENCIL' and dup_obj != plane and dup_obj != puck:
#                    for layer in gp_obj.data.layers:
#                        if layer.info.startswith(dup_obj.name): # leads to issue where same name start causes double drivers to be added
#                            driver = layer.driver_add("hide").driver
#                            driver.type = 'SCRIPTED'
#                            # set the type first (default is 'SINGLE_PROP')
#                            var = driver.variables.new()
#                            var.type = 'LOC_DIFF'
#                            var.name = 'distance'
#                            var.targets[0].id = puck
#                            var.targets[0].data_path = 'location'
#                            var.targets[0].transform_space = 'TRANSFORM_SPACE'
#                            var.targets[1].id = dup_obj
#                            var.targets[1].data_path = 'location'
#                            var.targets[1].transform_space = 'TRANSFORM_SPACE'
#                            driver.expression = "distance > 0.1"

   # Add shrinkwrap constraint to the puck - Not necessary
                # shrinkwrap = puck.constraints.new(type='SHRINKWRAP')
                # shrinkwrap.target = plane
                # shrinkwrap.wrap_mode = 'ON_SURFACE'
                
#                #childof_dup_gp_face.childof_set_inverse(constraint="Child Of", owner='OBJECT')
#                for c in obj.constraints:
#                    if c.type == 'CHILD_OF':
#                        context_py = bpy.context.copy()
#                        context_py["constraint"] = c
#                        bpy.ops.constraint.childof_set_inverse(context_py, constraint="Child Of", owner='BONE')
