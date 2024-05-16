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


no_of_face_items = 0

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
            self.report({'INFO'}, "New layer added and activated for drawing.")
            return {'FINISHED'}
        self.report({'ERROR'}, "Active object is not a Grease Pencil object.")
        return {'CANCELLED'}


class GPDoneDrawing(bpy.types.Operator):
    """Exit draw mode"""
    bl_idname = "gpencil.done_drawing"
    bl_label = "Done"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.active_object.select_set(True)
        bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}


class GPAddVerticesToGroup(bpy.types.Operator):
    """Add all vertices of the active Grease Pencil object to a vertex group with weight 1"""
    bl_idname = "gpencil.add_vertices_to_group"
    bl_label = "Add Vertices to Group"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        gp_obj = context.active_object
        if gp_obj and gp_obj.type == 'GPENCIL':
            # Create or get the vertex group
            vgroup_name = "GP Vertices"
            if vgroup_name not in gp_obj.vertex_groups:
                gp_obj.vertex_groups.new(name=vgroup_name)

            # Enter edit mode
            bpy.ops.object.mode_set(mode='EDIT_GPENCIL')

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

            # Return to paint mode
            bpy.ops.object.mode_set(mode='PAINT_GPENCIL')

            self.report({'INFO'}, "Vertices added to vertex group.")
            return {'FINISHED'}
        self.report({'ERROR'}, "Active object is not a Grease Pencil object.")
        return {'CANCELLED'}

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
            root_bone.head= (0, 0, 0)
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

class FinishMouthShape(bpy.types.Operator):
    """Duplicate the GP object, scale it, move it, and prepare the original for new drawing"""
    bl_idname = "gpencil.finish_mouth_shape"
    bl_label = "Finish Mouth Shape"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Get the active object
        gp_obj = context.active_object
        if gp_obj and gp_obj.type == 'GPENCIL':
            # Duplicate the Grease Pencil object
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            gp_obj.select_set(True)
            bpy.ops.object.duplicate()
            gp_duplicate = context.active_object

            # Scale the duplicate to be a bit smaller
            gp_duplicate.scale *= 0.2
            # Get the count of finished mouth shapes
            count = context.scene.finish_mouth_count

            # Calculate the position based on count (4 per row, then next row)
            row_length = 4
            x_offset = (count % row_length) * .5
            y_offset = (count // row_length) * -.5

            # Move the duplicate to the calculated position
            gp_duplicate.location.x += x_offset
            gp_duplicate.location.y += y_offset

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
        layout = self.layout
        obj = context.object

        if obj is None or obj.type != 'GPENCIL' or context.mode not in {'PAINT_GPENCIL', 'EDIT_GPENCIL'}:
            layout.operator(ViewCenterOrigin.bl_idname, text="Create Grease Pencil")

        if obj and obj.type == 'GPENCIL' and context.mode in {'PAINT_GPENCIL', 'EDIT_GPENCIL'}:
            layout.operator(GPAddNewLayer.bl_idname, text="New Layer")
            layout.operator(GPAddVerticesToGroup.bl_idname, text="Add Vertices to Group")
            layout.operator(GPDoneDrawing.bl_idname, text="Done")
            layout.operator(FinishMouthShape.bl_idname, text="Finish Mouth Shape")

        if obj is None or obj.type != 'GPENCIL' or context.mode not in {'PAINT_GPENCIL', 'EDIT_GPENCIL'}:
            layout.operator(CreateRig.bl_idname, text="Create Rig")


# Registration

def register():
    bpy.utils.register_class(ViewCenterOrigin)
    bpy.utils.register_class(ToolsPanel)
    bpy.utils.register_class(GPAddNewLayer)
    bpy.utils.register_class(GPAddVerticesToGroup)
    bpy.utils.register_class(CreateRig)
    bpy.utils.register_class(GPDoneDrawing)
    bpy.utils.register_class(FinishMouthShape)

    bpy.types.Scene.finish_mouth_count = bpy.props.IntProperty(name="Finish Mouth Count", default=0)
def unregister():
    bpy.utils.unregister_class(ViewCenterOrigin)
    bpy.utils.unregister_class(ToolsPanel)
    bpy.utils.unregister_class(GPAddNewLayer)
    bpy.utils.unregister_class(GPAddVerticesToGroup)
    bpy.utils.unregister_class(CreateRig)
    bpy.utils.unregister_class(GPDoneDrawing)
    bpy.utils.unregister_class(FinishMouthShape)
    del bpy.types.Scene.finish_mouth_count

if __name__ == "__main__":
    register()

