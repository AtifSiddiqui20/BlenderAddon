bl_info = {
    "name": "View and Movement Tools",
    "author": "Attaboy!",
    "version": (0, 0, 1),
    "blender": (3, 6, 0),
    "category": "Grease Pencil",
    "location": "View 3D > Tool Shelf > My Tools",
    "description": "Create and edit 2d faces with Grease Pencil",
}

import bpy
import bmesh
import os
import math

# Operator to center view on the world origin
class ViewCenterOrigin(bpy.types.Operator):
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
            plane.scale = (2, 1, 1)
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


class GPDoneDrawing(bpy.types.Operator):
    """Exit draw mode and arrange duplicated GP objects"""
    bl_idname = "gpencil.done_drawing"
    bl_label = "Done"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.active_object.select_set(True)
        gp_obj = context.active_object
        if gp_obj and gp_obj.type == 'GPENCIL':
            # Create or get the vertex group
            vgroup_name = "GP Vertices"
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
            spacing_z = .2
            items_per_row = 4

            # Initialize the position variables
            x = 2.0
            z = 2.0
            plsize = 0  # initialize the plane size

            # Iterate through the objects in the collection
            for index, obj in enumerate(collection.objects):
                # Set the object's location
                obj.location.x = x
                obj.location.z = z
                obj.hide_viewport = False


                # Update the x position for the next object
                x += spacing_x

                # Check if we need to move to the next row
                if (index + 1) % items_per_row == 0:
                    x = 2.0  # Reset x position for the new row
                    z -= spacing_z  # Move to the next row
                    plsize += 1     # Increment the plane's z scaling

            # Create Another Plane and resize it to the size of the mouths
            bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=True, location=(2, 0, 2), rotation=(1.5708, 0, 0))
            
            plane.name = "Mouths Control Board Plane"
            if plsize != 0:
                plane.scale = (1.8, plsize / 2, plsize / 2)
            else:
                plane.scale = (1.8, .403, .403)
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
            plane.location.z = 2.2

            # Make the plane unselectable and change its display type to wire
            plane.display_type = 'WIRE'
            # plane.hide_select = True
            plane.hide_render = True

            # Add the plane to the "Mouth Rig Control Board Objects" collection
            collection.objects.link(plane)
            context.collection.objects.unlink(plane)

            # Hide everything in the collection from render view
            for obj in collection.objects:
                obj.hide_render = True
                # Parent everything in the collection to the plane
                if obj != plane:  
                    obj.parent = plane
                
            # Create a puck (mesh circle) and place it on top of the first duplicated object
            first_dup_obj = collection.objects[0] if collection.objects else None
            if first_dup_obj:
                bpy.ops.mesh.primitive_circle_add(fill_type = 'NGON', vertices=16, radius=0.1, location=(first_dup_obj.location.x, first_dup_obj.location.y, first_dup_obj.location.z), rotation = (1.5708, 0, 0))
                puck = context.active_object
                puck.name = "Mouth Shape Control Selector"
                puck.hide_render = True
                collection.objects.link(puck)
                context.collection.objects.unlink(puck)
                
             # Add shrinkwrap constraint to the puck
                shrinkwrap = puck.constraints.new(type='SHRINKWRAP')
                shrinkwrap.target = plane
                shrinkwrap.wrap_mode = 'ON_SURFACE'
                puck.parent = plane

                
            # Add drivers to control layer visibility
            for dup_index, dup_obj in enumerate(collection.objects):
                if dup_obj.type == 'GPENCIL' and dup_obj != plane and dup_obj != puck:
                    for layer in gp_obj.data.layers:
                        if layer.info.startswith(dup_obj.name):
                            driver = layer.driver_add("hide").driver
                            driver.type = 'SCRIPTED'
                            # set the type first (default is 'SINGLE_PROP')
                            var = driver.variables.new()
                            var.type = 'LOC_DIFF'
                            var.name = 'distance'
                            var.targets[0].id = puck
                            var.targets[0].data_path = 'location'
                            var.targets[1].id = dup_obj
                            var.targets[1].data_path = 'location'
                            driver.expression = "distance > 0.1"

               

            # Return to Gpencil object
            bpy.ops.object.select_all(action='DESELECT')
            gp_obj.select_set(True)
            context.view_layer.objects.active = gp_obj

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
        # Get the active object
        gp_obj = context.active_object
        if gp_obj and gp_obj.type == 'GPENCIL':
            vgroup_name = "GP Vertices"
            if vgroup_name not in gp_obj.vertex_groups:
                self.report({'ERROR'}, f"Vertex group '{vgroup_name}' not found.")
                return {'CANCELLED'}

            # Create a new armature object
            bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
            armature = context.object
            armature.name = "GP_Rig"
            bpy.ops.object.mode_set(mode='EDIT')

            # Access the armature's edit bones
            bones = armature.data.edit_bones

            # Create the root bone, it's size is based on the GP object
            root_bone = bones[0]
            root_bone.name = "root"
            root_bone.head = (0, 0, 0)
            root_bone.tail = (0, 0, 0.5)

            # Create the named bone
            named_bone = bones.new(vgroup_name)
            named_bone.head = (0, 0, 0.5)
            named_bone.tail = (0, 0, 1)
            named_bone.parent = root_bone
            named_bone.use_connect = False

            # Switch back to object mode
            bpy.ops.object.mode_set(mode='OBJECT')

            # Parent the GP object to the armature with automatic weights
            gp_obj.select_set(True)
            armature.select_set(True)
            context.view_layer.objects.active = armature
            bpy.ops.object.parent_set(type='ARMATURE')

            # Add the armature to the same collection as the Grease Pencil object
            collection = gp_obj.users_collection[0]
            if armature.users_collection:
                for coll in armature.users_collection:
                    coll.objects.unlink(armature)
            collection.objects.link(armature)

            self.report({'INFO'}, "Rig created with two bones.")
            return {'FINISHED'}
        self.report({'ERROR'}, "Active object is not a Grease Pencil object.")
        return {'CANCELLED'}


class GreasePencilFaceRigSettings(bpy.types.PropertyGroup):
    mouth_shape_name: bpy.props.StringProperty(
        name="Mouth Shape Name",
        description="Enter a name for the mouth shape",
        default="",
        maxlen=25,
    )

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
            gp_duplicate.hide_viewport = True
            # Set gp_duplicate name to the provided mouth shape name
            gp_duplicate.name = mouth_name

            # Scale the duplicate
            gp_duplicate.scale *= 0.2

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

            # Link the duplicated object to the new collection
            new_collection.objects.link(gp_duplicate)
            parent_collection.objects.unlink(gp_duplicate)
            # context.collection.objects.unlink(gp_duplicate)
            # Get the count of finished mouth shapes
            count = context.scene.finish_mouth_count

            # Increment the count
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






# Panel to hold the buttons
class ToolsPanel(bpy.types.Panel):
    """Creates a Panel in the viewport for GP Face Tools"""
    bl_label = "Grease Pencil Face Tools"
    bl_idname = "VIEW3D_PT_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'My Tools'

    def draw(self, context):
        name = context.scene.grease_pencil_face_rig_settings
        layout = self.layout
        obj = context.object

        if obj is None or obj.type != 'GPENCIL' or context.mode not in {'PAINT_GPENCIL', 'EDIT_GPENCIL'}:
            layout.operator(ViewCenterOrigin.bl_idname, text="Create Grease Pencil")

        if obj and obj.type == 'GPENCIL' and context.mode in {'PAINT_GPENCIL', 'EDIT_GPENCIL'}:
            layout.operator(GPAddNewLayer.bl_idname, text="New Layer")
            # layout.operator(GPAddVerticesToGroup.bl_idname, text="Add Vertices to Group")
            # Add text field and Finish Mouth Shape operator
            row = layout.row()
            row.prop(name, "mouth_shape_name")
            layout.operator(FinishMouthShape.bl_idname, text="Finish Mouth Shape")
            
            layout.operator(GPDoneDrawing.bl_idname, text="Done")
        if obj is None or obj.type != 'GPENCIL' or context.mode not in {'PAINT_GPENCIL', 'EDIT_GPENCIL'}:
            layout.operator(CreateRig.bl_idname, text="Create Rig")


# Registration


classes = (
    GreasePencilFaceRigSettings,
    FinishMouthShape,
    ViewCenterOrigin,
    ToolsPanel,
    GPAddNewLayer,
    CreateRig,
    GPDoneDrawing
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    

    bpy.types.Scene.finish_mouth_count = bpy.props.IntProperty(name="Finish Mouth Count", default=0)
    bpy.types.Scene.face_layers = bpy.props.IntProperty(name="Face Layer Count", default=1)
    bpy.types.Scene.grease_pencil_face_rig_settings = bpy.props.PointerProperty(type=GreasePencilFaceRigSettings)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.finish_mouth_count
    del bpy.types.Scene.face_layers
    del bpy.types.Scene.grease_pencil_face_rig_settings


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