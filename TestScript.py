bl_info = {
    "name": "View and Movement Tools",
    "author" : "Attaboy!",
    "blender": (3, 60, 0),
    "category": "Grease Pencil",
    "location": "View 3D > Tool Shelf > My Tools",
    "description": "Create and edit 2d faces with Grease Pencil",
}

import bpy

# Operator to move objects along X-axis
class ObjectMoveX(bpy.types.Operator):
    """Move Object by 1 on X"""
    bl_idname = "object.move_x"
    bl_label = "Move X by One"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        for obj in scene.objects:
            obj.location.x += 1.0
        return {'FINISHED'}

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
            bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=False, location=(0, 0, 0), rotation=(1.5708, 0, 0))
            plane = context.active_object
            plane.name = plane_name
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
            gp_mat.grease_pencil.color = (0,0,0,1)

            gp_data.materials.append(gp_mat)
            bpy.ops.gpencil.draw(wait_for_input =False)
            
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
                        override = {'area': area, 'region': region, 'space_data': area.spaces.active, 'region_3d': area.spaces.active.region_3d}
                        bpy.ops.view3d.view_selected(override)
                        obj.hide_select=True 
                        break

    def make_plane_unselectable(self, obj):
        # Get the object by name and check if it is not None
        if bpy.context.view_layer.objects.get(obj.name) is not None:
            obj.hide_select = True


    def create_default_gp_material(self, gp_obj):
        # Create a new material
        mat = bpy.data.materials.new(name="GP Default Material")
        mat_gp = mat.grease_pencil
        if not mat_gp:
            mat_gp = mat.grease_pencil

        # Add the material to the grease pencil data
        gp_obj.data.materials.append(mat)

        # Set up the material properties
        mat_gp.color = (0.4, 0.2, 0.8, 1.0)



        
# Panel to hold the buttons
class ToolsPanel(bpy.types.Panel):
    """Creates a Panel in the viewport for view and movement tools"""
    bl_label = "View and Movement Tools"
    bl_idname = "VIEW3D_PT_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'My Tools'

    def draw(self, context):
        layout = self.layout
        layout.operator(ObjectMoveX.bl_idname, text="Move X by One")
        layout.operator(ViewCenterOrigin.bl_idname, text="Create Plane on Origin")

# Registration
def register():
    bpy.utils.register_class(ObjectMoveX)
    bpy.utils.register_class(ViewCenterOrigin)
    bpy.utils.register_class(ToolsPanel)

def unregister():
    bpy.utils.unregister_class(ObjectMoveX)
    bpy.utils.unregister_class(ViewCenterOrigin)
    bpy.utils.unregister_class(ToolsPanel)

if __name__ == "__main__":
    register()
