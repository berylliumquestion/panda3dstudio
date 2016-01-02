from ..base import *
from panda3d.fx import ProjectionScreen
from math import pi, sin, cos


class TexProjectorEdgeManager(ObjectManager, PickingColorIDManager):

    def __init__(self):

        ObjectManager.__init__(self, "tex_proj_edge", self.__create_proj_edge, "sub",
                               pickable=True)
        PickingColorIDManager.__init__(self)
        PickableTypes.add("tex_proj_edge")

    def __create_proj_edge(self, projector, axis, corner_index):

        picking_col_id = self.get_next_picking_color_id()
        proj_edge = TexProjectorEdge(
            projector, axis, corner_index, picking_col_id)

        return proj_edge, picking_col_id


class TexProjectorManager(ObjectManager, CreationPhaseManager, ObjPropDefaultsManager):

    def __init__(self):

        ObjectManager.__init__(self, "tex_projector",
                               self.__create_tex_projector)
        CreationPhaseManager.__init__(self, "tex_projector")
        ObjPropDefaultsManager.__init__(self, "tex_projector")

        self.set_property_default("on", True)
        self.set_property_default("size", 1.)
        self.set_property_default("film_w", 1.)
        self.set_property_default("film_h", 1.)
        self.set_property_default("film_x", 0.)
        self.set_property_default("film_y", 0.)
        self.set_property_default("projection_type", "orthographic")

        self._draw_plane = None

        self._pixel_under_mouse = VBase4()
        self._item_is_under_mouse = None
        self._target_to_projector_ids = {}

        Mgr.accept("inst_create_tex_projector",
                   self.__create_projector_instantly)
        Mgr.accept("register_texproj_targets",
                   self.__register_projection_targets)
        Mgr.accept("unregister_texproj_targets",
                   self.__unregister_projection_targets)
        Mgr.add_app_updater("texproj_prop", self.__set_projector_property,
                            kwargs=["target_id", "target_prop"])
        Mgr.add_app_updater("uv_projection", self.__apply_uvs)
        Mgr.add_app_updater("remove_texproj_target",
                            self.__remove_projection_target)
        Mgr.add_app_updater("object_removal", self.__remove_projection_target)

    def setup(self):

        sort = PendingTasks.get_sort("set_obj_level", "object")

        if sort is None:
            return False

        PendingTasks.add_task_id("update_texproj", "object", sort + 1)

        creation_phases = []
        creation_phase = (self.__start_creation_phase1, self.__creation_phase1)
        creation_phases.append(creation_phase)

        status_text = {}
        status_text["obj_type"] = "texture projector"
        status_text["phase1"] = "draw out the projector"

        CreationPhaseManager.setup(self, creation_phases, status_text)

        add_state = Mgr.add_state
        add_state("texprojtarget_picking_mode", -10,
                  self.__enter_picking_mode, self.__exit_picking_mode)

        bind = Mgr.bind_state
        bind("texprojtarget_picking_mode", "pick texproj target -> navigate", "space",
             lambda: Mgr.enter_state("navigation_mode"))
        bind("texprojtarget_picking_mode",
             "pick texproj target", "mouse1", self.__pick)
        bind("texprojtarget_picking_mode", "exit texproj target picking", "escape",
             lambda: Mgr.exit_state("texprojtarget_picking_mode"))
        bind("texprojtarget_picking_mode", "cancel texproj target picking", "mouse3-up",
             lambda: Mgr.exit_state("texprojtarget_picking_mode"))

        status_data = Mgr.get_global("status_data")
        mode_text = "Pick projector target"
        info_text = "LMB to pick object; RMB to end"
        status_data["pick_texproj_target"] = {
            "mode": mode_text, "info": info_text}

        return True

    def __enter_picking_mode(self, prev_state_id, is_active):

        Mgr.add_task(self.__update_cursor, "update_tpt_picking_cursor")
        Mgr.update_app("status", "pick_texproj_target")

    def __exit_picking_mode(self, next_state_id, is_active):

        self._item_is_under_mouse = None  # neither False nor True, to force an
        # update of the cursor next time
        # self.__update_cursor() is called
        Mgr.remove_task("update_tpt_picking_cursor")
        Mgr.set_cursor("main")

    def __pick(self):

        target = Mgr.get("object", pixel_color=self._pixel_under_mouse)

        if target and target.get_type() == "model":

            projectors = [obj for obj in Mgr.get("selection", "top")
                          if obj.get_type() == "tex_projector"]

            if len(projectors) == 1:
                projector = projectors[0]
                target_id = target.get_id()
                projector.add_target(target_id)
                self.__register_projection_targets(
                    [target_id], projector.get_id())

    def __update_cursor(self, task):

        self._pixel_under_mouse = Mgr.get("pixel_under_mouse")
        item_is_under_mouse = self._pixel_under_mouse != VBase4()

        if item_is_under_mouse != self._item_is_under_mouse:
            self._item_is_under_mouse = item_is_under_mouse
            Mgr.set_cursor("select" if item_is_under_mouse else "main")

        return task.cont

    def __apply_uvs(self):

        projectors = [obj for obj in Mgr.get("selection", "top")
                      if obj.get_type() == "tex_projector"]

        if len(projectors) == 1:
            projectors[0].apply_uvs()

    def __register_projection_targets(self, target_ids, projector_id, restore=False):

        target_to_proj_ids = self._target_to_projector_ids

        for target_id in target_ids:

            if not restore:

                if target_id in target_to_proj_ids:

                    old_projector_id = target_to_proj_ids[target_id]

                    if old_projector_id != projector_id:
                        projector = Mgr.get("tex_projector", old_projector_id)
                        projector.remove_target(target_id)

            target_to_proj_ids[target_id] = projector_id

    def __unregister_projection_targets(self, target_ids):

        target_to_proj_ids = self._target_to_projector_ids

        for target_id in target_ids:
            if target_id in target_to_proj_ids:
                del target_to_proj_ids[target_id]

    def __remove_projection_target(self, target_id, add_to_hist=True):

        target_to_proj_ids = self._target_to_projector_ids

        if target_id in target_to_proj_ids:
            projector_id = target_to_proj_ids[target_id]
            projector = Mgr.get("tex_projector", projector_id)
            projector.remove_target(target_id, add_to_hist)
            del target_to_proj_ids[target_id]

    def __create_projector_instantly(self, origin_pos):

        projector_id = self.generate_object_id()
        obj_type = self.get_object_type()
        name = Mgr.get("next_obj_name", obj_type)
        projector = Mgr.do("create_tex_projector",
                           projector_id, name, origin_pos)
        prop_defaults = self.get_property_defaults()
        projector.set_size(prop_defaults["size"])
        Mgr.update_remotely("next_obj_name", Mgr.get(
            "next_obj_name", obj_type))
        # make undo/redoable
        self.add_history(projector)

    def __create_tex_projector(self, projector_id, name, origin_pos):

        prop_defaults = self.get_property_defaults()
        projector = TexProjector(projector_id, name, origin_pos,
                                 prop_defaults["on"],
                                 prop_defaults["projection_type"],
                                 prop_defaults["film_w"],
                                 prop_defaults["film_h"],
                                 prop_defaults["film_x"],
                                 prop_defaults["film_y"])

        return projector, projector_id

    def __start_creation_phase1(self):
        """ start drawing out texture projector """

        projector_id = self.generate_object_id()
        name = Mgr.get("next_obj_name", self.get_object_type())
        origin_pos = self.get_origin_pos()
        projector = Mgr.do("create_tex_projector",
                           projector_id, name, origin_pos)
        self.init_object(projector)

        # Create the plane parallel to the camera and going through the projector
        # origin, used to determine the size drawn by the user.

        normal = self.world.get_relative_vector(self.cam, Vec3(0., 1., 0.))
        grid_origin = Mgr.get(("grid", "origin"))
        pos = self.world.get_relative_point(grid_origin, origin_pos)
        self._draw_plane = Plane(normal, pos)

    def __creation_phase1(self):
        """ Draw out texture projector """

        mpos = self.mouse_watcher.get_mouse()
        far_point_local = Point3()
        self.cam_lens.extrude(mpos, Point3(), far_point_local)
        far_point = self.world.get_relative_point(self.cam, far_point_local)
        cam_pos = self.cam.get_pos(self.world)
        intersection_point = Point3()
        self._draw_plane.intersects_line(
            intersection_point, cam_pos, far_point)
        grid_origin = Mgr.get(("grid", "origin"))
        pos = self.world.get_relative_point(grid_origin, self.get_origin_pos())
        size = max(.001, (intersection_point - pos).length())
        self.get_object().set_size(size)

    def __set_projector_property(self, prop_id, value, projector_id=None,
                                 add_to_hist=True, target_id=None, target_prop=""):

        if projector_id:
            objs = [Mgr.get("tex_projector", projector_id)]
        else:
            objs = Mgr.get("selection")

        if not objs:
            return

        changed_objs = [
            obj for obj in objs if obj.set_property(prop_id, value)]

        PendingTasks.handle(["object", "ui"], True)

        if not changed_objs:
            return

        if not add_to_hist:
            return

        Mgr.do("update_history_time")

        obj_data = {}

        for obj in changed_objs:
            obj_data[obj.get_id()] = obj.get_data_to_store(
                "prop_change", prop_id)

        if prop_id == "on":

            if len(changed_objs) == 1:
                obj = changed_objs[0]
                event_descr = 'Turn %s "%s"' % (
                    "on" if value else "off", obj.get_name())
            else:
                event_descr = 'Turn %s texture projectors:\n' % (
                    "on" if value else "off")
                event_descr += "".join(['\n    "%s"' %
                                        obj.get_name() for obj in changed_objs])

        elif prop_id == "targets":

            model = Mgr.get("model", target_id)
            target_name = model.get_name() if model else ""

            if target_id in value:
                target_data = value[target_id]

            if target_prop == "add":
                event_descr = 'Add projection target to "%s":\n' % obj.get_name()
                event_descr += '\n    "%s"' % target_name
            elif target_prop == "remove":
                if target_name:
                    event_descr = 'Remove projection target from "%s":\n' % obj.get_name()
                    event_descr += '\n    "%s"' % target_name
                else:
                    event_descr = 'Remove deleted projection target from "%s"' % obj.get_name()
            elif target_prop == "clear":
                event_descr = 'Clear projection targets from "%s"' % obj.get_name()
            elif target_prop == "use_poly_sel":
                event_descr = 'Change projection property of "%s"' % obj.get_name()
                event_descr += '\nfor target "%s":\n' % target_name
                event_descr += "\n    project onto %s" % ("entire target" if target_data[
                                                          "toplvl"] else "selected polys only")
            elif target_prop == "show_poly_sel":
                event_descr = 'Change projection property of "%s"' % obj.get_name()
                event_descr += '\nfor target "%s":\n' % target_name
                event_descr += "\n    %s selection state of affected polys" % (
                    "show" if target_data["show_poly_sel"] else "hide")
            elif target_prop == "uv_set_ids":
                uv_set_id_str = str(target_data["uv_set_ids"]).strip("(),")
                event_descr = 'Change projection property of "%s"' % obj.get_name()
                event_descr += '\nfor target "%s":\n' % target_name
                event_descr += "\n    affect UV sets: %s" % uv_set_id_str

        else:

            if prop_id == "projection_type":
                prop_descr = "projection type"
            elif prop_id == "film_w":
                prop_descr = "film width"
            elif prop_id == "film_h":
                prop_descr = "film height"
            elif prop_id == "film_x":
                prop_descr = "film X offset"
            elif prop_id == "film_y":
                prop_descr = "film Y offset"
            else:
                prop_descr = prop_id

            if len(changed_objs) == 1:
                obj = changed_objs[0]
                event_descr = 'Change %s of "%s"\nto %s' % (
                    prop_descr, obj.get_name(), value)
            else:
                event_descr = 'Change %s of texture projectors:\n' % prop_descr
                event_descr += "".join(['\n    "%s"' %
                                        obj.get_name() for obj in changed_objs])
                event_descr += '\n\nto %s' % value

        event_data = {"objects": obj_data}

        Mgr.do("add_history", event_descr, event_data, update_time_id=False)


class TexProjectorEdge(BaseObject):

    def __init__(self, projector, axis, corner_index, picking_col_id):

        self._projector = projector
        self._axis = axis
        self._corner_index = corner_index
        self._picking_col_id = picking_col_id

    def destroy(self):

        Mgr.do("unregister_tex_proj_edge", self._id)

    def get_toplevel_object(self):

        return self._projector

    def get_picking_color_id(self):

        return self._picking_col_id

    def get_point_at_screen_pos(self, screen_pos):

        body = self._projector.get_body()
        corner_pos = self._projector.get_corner_pos(self._corner_index)
        vec_coords = [0., 0., 0.]
        vec_coords["XYZ".index(self._axis)] = 1.
        edge_vec = V3D(self.world.get_relative_vector(body, Vec3(*vec_coords)))
        cam_vec = V3D(self.world.get_relative_vector(
            self.cam, Vec3(0., 1., 0.)))
        cross_vec = edge_vec ** cam_vec

        if not cross_vec.normalize():
            return corner_pos

        point1 = corner_pos
        point2 = point1 + edge_vec
        point3 = point1 + cross_vec

        far_point_local = Point3()
        self.cam_lens.extrude(screen_pos, Point3(), far_point_local)
        far_point = self.world.get_relative_point(self.cam, far_point_local)
        cam_pos = self.cam.get_pos(self.world)

        plane = Plane(point1, point2, point3)
        intersection_point = Point3()

        if not plane.intersects_line(intersection_point, cam_pos, far_point):
            return

        return intersection_point


class TexProjector(TopLevelObject):

    def __getstate__(self):

        d = self.__dict__.copy()
        d["_origin"] = NodePath(self.get_origin().get_name())
        d["_subobj_root"] = NodePath("subobj_root")
        d["_size"] = 1.

        return d

    def __setstate__(self, state):

        self.__dict__ = state

        origin = self.get_origin()
        origin.reparent_to(Mgr.get("object_root"))
        origin.set_light_off()
        origin.set_texture_off()
        origin.set_material_off()
        origin.set_shader_off()
        subobj_root = self._subobj_root
        subobj_root.reparent_to(origin)
        subobj_root.set_color_scale(.1)
        subobj_root.set_bin("fixed", 50)
        subobj_root.set_depth_test(False)
        subobj_root.set_depth_write(False)
        self._body.reparent_to(subobj_root)
        self._lens_np.reparent_to(subobj_root)
        self._tripod.reparent_to(subobj_root)

        for np in self._lens_viz.itervalues():
            np.reparent_to(subobj_root)

    def __init__(self, projector_id, name, origin_pos, on, projection_type,
                 film_w, film_h, film_x, film_y):

        prop_ids = ["on", "size", "film_w", "film_h", "film_x", "film_y",
                    "projection_type", "targets"]

        TopLevelObject.__init__(self, "tex_projector", projector_id, name, origin_pos,
                                has_color=False)

        self._type_prop_ids = prop_ids
        self._is_on = on
        self._size = 0.
        self._film_w = 1.
        self._film_h = 1.
        self._film_x = 0.
        self._film_y = 0.
        self._projection_type = projection_type
        self._targets = {}

        self._corners = []
        self._edges = {}

        origin = self.get_origin()
        origin.set_light_off()
        origin.set_texture_off()
        origin.set_material_off()
        origin.set_shader_off()

        self._subobj_root = origin.attach_new_node("subobj_root")
        self._body = None
        self._lens_viz = {}
        self._tripod = None

        self._lenses = {"orthographic": OrthographicLens(
        ), "perspective": PerspectiveLens()}
        lens_node = LensNode("tex_proj_lens", self._lenses[projection_type])
        self._lens_np = self._subobj_root.attach_new_node(lens_node)

        for lens in self._lenses.itervalues():
            lens.set_film_size(1., 1.)
            lens.set_focal_length(1.5)

        edge_verts = self.__create_body()
        self.__create_lens_viz(edge_verts)
        self.__create_tripod()
        self._lens_viz[projection_type].show()
        self.set_film_width(film_w)
        self.set_film_height(film_h)
        self.set_film_offset_x(film_x)
        self.set_film_offset_y(film_y)

        self._subobj_root.set_color_scale(.1)
        self._subobj_root.set_bin("fixed", 50)
        self._subobj_root.set_depth_test(False)
        self._subobj_root.set_depth_write(False)

    def __create_body(self):

        minmax = (-.5, .5)
        corners = [(x, y, z) for x in minmax for y in minmax for z in minmax]

        x1, y1, z1 = origin1 = corners.pop()
        edge_origins = [origin1]

        for corner in corners[:]:

            x, y, z = corner

            if (x == x1 and y != y1 and z != z1) \
                    or (y == y1 and x != x1 and z != z1) \
                    or (z == z1 and x != x1 and y != y1):

                edge_origins.append(corner)
                corners.remove(corner)

                if len(corners) == 4:
                    break

        self._corners = edge_origins + corners
        edge_verts = []
        edge_data = []
        pickable_type_id = PickableTypes.get_id("tex_proj_edge")

        for i, corner1 in enumerate(edge_origins):

            x1, y1, z1 = corner1

            for corner2 in corners:

                x2, y2, z2 = corner2

                if (x1 == x2 and y1 == y2):
                    axis = "Z"
                elif (x1 == x2 and z1 == z2):
                    axis = "Y"
                elif (y1 == y2 and z1 == z2):
                    axis = "X"
                else:
                    continue

                j = self._corners.index(corner2)
                edge = Mgr.do("create_tex_proj_edge", self, axis, i)
                color_id = edge.get_picking_color_id()
                picking_color = get_color_vec(color_id, pickable_type_id)
                self._edges[color_id] = edge
                vert_ids = (i, j)
                edge_verts.append(vert_ids)
                edge_data.append((vert_ids, picking_color))

        vertex_format = GeomVertexFormat.get_v3n3cpt2()
        vertex_data = GeomVertexData(
            "tex_proj_body_data", vertex_format, Geom.UH_static)

        pos_writer = GeomVertexWriter(vertex_data, "vertex")
        col_writer = GeomVertexWriter(vertex_data, "color")

        lines = GeomLines(Geom.UH_static)

        for indices, color in edge_data:

            for index in indices:
                pos = self._corners[index]
                pos_writer.add_data3f(pos)
                col_writer.add_data4f(color)

            lines.add_next_vertices(2)

        geom = Geom(vertex_data)
        geom.add_primitive(lines)
        geom_node = GeomNode("tex_proj_body")
        geom_node.add_geom(geom)

        body = self._subobj_root.attach_new_node(geom_node)
        body.set_scale(1.2, 1.8, 1.2)
        body.set_color(.7, 1., .7, 1.)
        self._body = body

        return edge_verts

    def __create_lens_viz(self, edge_verts):

        def xform_point(point, proj_type):

            if proj_type == "orthographic":

                x, y, z = point
                y = (y + .5) * .5 + .9

            elif proj_type == "perspective":

                x, y, z = point
                y = (y + .5) * .5 + .9
                x *= y * .6666
                z *= y * .6666

            return (x, y, z)

        for proj_type in ("orthographic", "perspective"):

            corners = [xform_point(pos, proj_type) for pos in self._corners]

            vertex_format = GeomVertexFormat.get_v3n3cpt2()
            vertex_data = GeomVertexData("tex_proj_lens_%s_viz_data" % proj_type,
                                         vertex_format, Geom.UH_static)

            pos_writer = GeomVertexWriter(vertex_data, "vertex")

            for pos in corners:
                pos_writer.add_data3f(pos)

            line = GeomLines(Geom.UH_static)

            for i, j in edge_verts:
                line.add_vertices(i, j)

            geom = Geom(vertex_data)
            geom.add_primitive(line)
            geom_node = GeomNode("tex_proj_lens_%s_viz" % proj_type)
            geom_node.add_geom(geom)

            lens_viz = self._subobj_root.attach_new_node(geom_node)
            lens_viz.hide(Mgr.get("picking_mask"))
            lens_viz.hide()
            lens_viz.set_color(.5, .8, .5, 1.)
            self._lens_viz[proj_type] = lens_viz

    def __create_tripod(self):

        angle = 2. * pi / 3.
        positions = [Point3(sin(angle * i), cos(angle * i), -1.5)
                     for i in xrange(3)]

        vertex_format = GeomVertexFormat.get_v3n3cpt2()
        vertex_data = GeomVertexData(
            "tex_proj_tripod_data", vertex_format, Geom.UH_static)

        pos_writer = GeomVertexWriter(vertex_data, "vertex")

        line = GeomLines(Geom.UH_static)

        pos_writer.add_data3f(0., 0., 0.)

        for i, pos in enumerate(positions):
            pos_writer.add_data3f(pos)
            line.add_vertices(0, i + 1)

        geom = Geom(vertex_data)
        geom.add_primitive(line)
        geom_node = GeomNode("tex_proj_tripod")
        geom_node.add_geom(geom)

        tripod = self._subobj_root.attach_new_node(geom_node)
        tripod.hide(Mgr.get("picking_mask"))
        tripod.set_z(-.6)
        tripod.set_color(.5, .8, .5, 1.)
        self._tripod = tripod

    def destroy(self, add_to_hist=True):

        TopLevelObject.destroy(self, add_to_hist)

        if self.is_selected():

            for target_id, target_data in self._targets.iteritems():

                model = Mgr.get("model", target_id)

                if model:
                    uv_set_ids = target_data["uv_set_ids"]
                    toplvl = target_data["toplvl"]
                    target = model.get_geom_object().get_geom_data_object()
                    target.project_uvs(uv_set_ids, False, toplvl=toplvl)

        self.unregister()
        self._edges = {}

        for np in self._lens_viz.itervalues():
            np.remove_node()

        self._lens_viz = {}
        self._lens_np.remove_node()
        self._lens_np = None
        self._subobj_root.remove_node()
        self._subobj_root = None
        self._body = None
        self._tripod = None

    def get_subobject_root(self):

        return self._subobj_root

    def get_body(self):

        return self._body

    def get_corner_pos(self, corner_index):

        corner_pos = Point3(self._corners[corner_index])

        return self.world.get_relative_point(self._body, corner_pos)

    def get_toplevel_object(self):

        return self

    def register(self):

        TopLevelObject.register(self)

        obj_type = "tex_proj_edge"
        Mgr.do("register_%s_objs" % obj_type, self._edges.itervalues())

    def unregister(self):

        obj_type = "tex_proj_edge"
        Mgr.do("unregister_%s_objs" % obj_type, self._edges.itervalues())
        Mgr.do("unregister_texproj_targets", self._targets.iterkeys())

    def set_on(self, on):

        if self._is_on == on:
            return False

        self._is_on = on

        if not self.is_selected():
            return True

        if on:

            for target_id, target_data in self._targets.iteritems():

                model = Mgr.get("model", target_id)

                if model:
                    uv_set_ids = target_data["uv_set_ids"]
                    toplvl = target_data["toplvl"]
                    show_poly_sel = target_data["show_poly_sel"]
                    target = model.get_geom_object().get_geom_data_object()
                    target.project_uvs(uv_set_ids, projector=self._lens_np, toplvl=toplvl,
                                       show_poly_sel=show_poly_sel)

        else:

            for target_id, target_data in self._targets.iteritems():

                model = Mgr.get("model", target_id)

                if model:
                    uv_set_ids = target_data["uv_set_ids"]
                    toplvl = target_data["toplvl"]
                    target = model.get_geom_object().get_geom_data_object()
                    target.project_uvs(uv_set_ids, False, toplvl=toplvl)

        return True

    def is_on(self):

        return self._is_on

    def set_size(self, size):

        if self._size == size:
            return False

        self._size = size
        self._subobj_root.set_scale(size)

        return True

    def get_size(self):

        return self._size

    def set_film_width(self, film_w):

        if self._film_w == film_w:
            return False

        self._film_w = film_w

        for lens in self._lenses.itervalues():
            lens.set_film_size(film_w, self._film_h)

        return True

    def get_film_width(self):

        return self._film_w

    def set_film_height(self, film_h):

        if self._film_h == film_h:
            return False

        self._film_h = film_h

        for lens in self._lenses.itervalues():
            lens.set_film_size(self._film_w, film_h)

        return True

    def get_film_height(self):

        return self._film_h

    def set_film_offset_x(self, film_x):

        if self._film_x == film_x:
            return False

        self._film_x = film_x

        for lens in self._lenses.itervalues():
            lens.set_film_offset(film_x, self._film_y)

        return True

    def get_film_offset_x(self):

        return self._film_x

    def set_film_offset_y(self, film_y):

        if self._film_y == film_y:
            return False

        self._film_y = film_y

        for lens in self._lenses.itervalues():
            lens.set_film_offset(self._film_x, film_y)

        return True

    def get_film_offset_y(self):

        return self._film_y

    def set_projection_type(self, projection_type):

        if self._projection_type == projection_type:
            return False

        self._lens_viz[self._projection_type].hide()
        self._lens_viz[projection_type].show()
        self._lens_np.node().set_lens(self._lenses[projection_type])
        self._projection_type = projection_type

        return True

    def get_projection_type(self):

        return self._projection_type

    def set_projection_targets(self, targets, restore=""):

        old_targets = self._targets

        if targets == old_targets:
            return False

        self._targets = targets

        old_target_ids = set(old_targets.keys())
        new_target_ids = set(targets.keys())
        common_target_ids = old_target_ids & new_target_ids

        if restore:
            Mgr.do("unregister_texproj_targets",
                   old_target_ids - new_target_ids)
            Mgr.do("register_texproj_targets", new_target_ids -
                   old_target_ids, self.get_id(), True)

        if self._is_on and self.is_selected():

            for target_id in old_target_ids - new_target_ids:

                model = Mgr.get("model", target_id)

                if model:
                    target_data = old_targets[target_id]
                    uv_set_ids = target_data["uv_set_ids"]
                    toplvl = target_data["toplvl"]
                    target = model.get_geom_object().get_geom_data_object()
                    target.project_uvs(uv_set_ids, False, toplvl=toplvl)

        if self._is_on and self.is_selected():

            for target_id in new_target_ids - old_target_ids:

                model = Mgr.get("model", target_id)

                if model:
                    target_data = targets[target_id]
                    uv_set_ids = target_data["uv_set_ids"]
                    toplvl = target_data["toplvl"]
                    show_poly_sel = target_data["show_poly_sel"]
                    target = model.get_geom_object().get_geom_data_object()
                    target.project_uvs(uv_set_ids, projector=self._lens_np, toplvl=toplvl,
                                       show_poly_sel=show_poly_sel)

        else:

            for target_id in common_target_ids:

                model = Mgr.get("model", target_id)

                if model:
                    target_data = old_targets[target_id]
                    uv_set_ids = target_data["uv_set_ids"]
                    toplvl = target_data["toplvl"]
                    target = model.get_geom_object().get_geom_data_object()
                    target.project_uvs(uv_set_ids, False, toplvl=toplvl)

            return True

        for target_id in common_target_ids:

            old_target_data = old_targets[target_id]
            new_target_data = targets[target_id]

            if new_target_data == old_target_data:
                continue

            model = Mgr.get("model", target_id)

            if model:

                old_uv_set_ids = set(old_target_data["uv_set_ids"])
                new_uv_set_ids = set(new_target_data["uv_set_ids"])
                old_uv_set_ids -= new_uv_set_ids
                old_uv_set_ids = tuple(sorted(old_uv_set_ids))
                new_uv_set_ids = new_target_data["uv_set_ids"]
                old_toplvl = old_target_data["toplvl"]
                new_toplvl = new_target_data["toplvl"]
                show_poly_sel = new_target_data["show_poly_sel"]
                target = model.get_geom_object().get_geom_data_object()

                if old_uv_set_ids:
                    target.project_uvs(
                        old_uv_set_ids, False, toplvl=old_toplvl)

                if new_toplvl != old_toplvl:
                    target.project_uvs(
                        new_uv_set_ids, False, toplvl=old_toplvl)

                target.project_uvs(new_uv_set_ids, projector=self._lens_np, toplvl=new_toplvl,
                                   show_poly_sel=show_poly_sel)

        return True

    def set_property(self, prop_id, value, restore=""):

        def update_app():

            if self.is_selected():
                Mgr.update_remotely("selected_obj_prop", "tex_projector", prop_id,
                                    self.get_property(prop_id, True))

        def restore_on(value):

            if self.set_on(value):
                update_app()

        def restore_proj_targets(value):

            if self.set_projection_targets(value, restore):
                update_app()

        if prop_id == "on":
            if restore:
                task = lambda: restore_on(value)
                task_id = "update_texproj"
                PendingTasks.add(task, task_id, "object",
                                 id_prefix="on_%s" % (self.get_id(),))
            elif self.set_on(value):
                update_app()
                return True
        elif prop_id == "size":
            if self.set_size(value):
                update_app()
                return True
        elif prop_id == "film_w":
            if self.set_film_width(value):
                update_app()
                return True
        elif prop_id == "film_h":
            if self.set_film_height(value):
                update_app()
                return True
        elif prop_id == "film_x":
            if self.set_film_offset_x(value):
                update_app()
                return True
        elif prop_id == "film_y":
            if self.set_film_offset_y(value):
                update_app()
                return True
        elif prop_id == "projection_type":
            if self.set_projection_type(value):
                update_app()
                return True
        elif prop_id == "targets":
            if restore:
                task = lambda: restore_proj_targets(value)
                task_id = "update_texproj"
                PendingTasks.add(task, task_id, "object",
                                 id_prefix="targets_%s" % (self.get_id(),))
            elif self.set_projection_targets(value):
                update_app()
                return True
        else:
            return TopLevelObject.set_property(self, prop_id, value, restore)

    def get_property(self, prop_id, for_remote_update=False):

        if prop_id == "on":
            return self._is_on
        elif prop_id == "size":
            return self._size
        elif prop_id == "film_w":
            return self._film_w
        elif prop_id == "film_h":
            return self._film_h
        elif prop_id == "film_x":
            return self._film_x
        elif prop_id == "film_y":
            return self._film_y
        elif prop_id == "projection_type":
            return self._projection_type
        elif prop_id == "targets":
            targets = dict((k, v.copy()) for k, v in self._targets.iteritems())
            if for_remote_update:
                target_names = dict((k, Mgr.get("model", k).get_name())
                                    for k in targets)
                targets = (targets, target_names)
            return targets

        return TopLevelObject.get_property(self, prop_id, for_remote_update)

    def get_property_ids(self):

        return TopLevelObject.get_property_ids(self) + self._type_prop_ids

    def get_type_property_ids(self):

        return self._type_prop_ids

    def add_target(self, target_id):

        uv_set_ids = (0,)
        targets = dict((k, v.copy()) for k, v in self._targets.iteritems())
        targets[target_id] = {"uv_set_ids": uv_set_ids,
                              "toplvl": True, "show_poly_sel": True}

        if self._is_on:
            target = Mgr.get("model", target_id).get_geom_object(
            ).get_geom_data_object()
            target.project_uvs(
                uv_set_ids, projector=self._lens_np, toplvl=True)

        Mgr.update_locally("texproj_prop", "targets", targets, self.get_id(), True,
                           target_id, "add")

    def remove_target(self, target_id, add_to_hist=True):

        targets = dict((k, v.copy()) for k, v in self._targets.iteritems())

        if self._is_on and self.is_selected():

            model = Mgr.get("model", target_id)

            if model:
                target_data = targets[target_id]
                uv_set_ids = target_data["uv_set_ids"]
                toplvl = target_data["toplvl"]
                target = model.get_geom_object().get_geom_data_object()
                target.project_uvs(uv_set_ids, False, toplvl=toplvl)

        del targets[target_id]
        Mgr.update_locally("texproj_prop", "targets", targets, self.get_id(), add_to_hist,
                           target_id, "remove")

    def apply_uvs(self):

        if not (self._is_on and self._targets):
            return

        obj_root = Mgr.get("object_root")
        screen = ProjectionScreen()
        screen_np = self.world.attach_new_node(screen)
        screen.set_projector(self._lens_np)
        uv_set_ids = set()
        geoms = {}
        targets = self._targets

        for target_id, target_data in targets.iteritems():
            uv_set_ids.update(target_data["uv_set_ids"])
            target = Mgr.get("model", target_id).get_geom_object(
            ).get_geom_data_object()
            origin = target.get_origin()
            geom = origin.find("**/toplevel_shaded_geom").copy_to(origin)
            geom.wrt_reparent_to(screen_np)
            geoms[target_id] = geom

        for uv_set_id in uv_set_ids:

            if uv_set_id:
                screen.set_texcoord_name(str(uv_set_id))

            screen.recompute()

        for target_id, target_data in targets.iteritems():
            geom = geoms[target_id]
            vertex_data = geom.node().get_geom(0).get_vertex_data()
            uv_set_ids = target_data["uv_set_ids"]
            toplvl = target_data["toplvl"]
            target = Mgr.get("model", target_id).get_geom_object(
            ).get_geom_data_object()
            target.project_uvs(uv_set_ids, False, toplvl=toplvl)
            target.apply_uv_projection(vertex_data, uv_set_ids, toplvl)

        screen_np.remove_node()

        # Add to history

        Mgr.do("update_history_time")
        names = []
        obj_data = {}

        for target_id in targets:
            obj = Mgr.get("model", target_id)
            names.append(obj.get_name())
            target = obj.get_geom_object().get_geom_data_object()
            obj_data[target_id] = target.get_data_to_store(
                "prop_change", "uvs")

        if len(targets) > 1:
            event_descr = 'Apply projected UVs to "%s" targets:\n' % self.get_name()
            event_descr += "".join(['\n    "%s"' % name for name in names])
        else:
            event_descr = 'Apply projected UVs to "%s" target:\n    "%s"' % (
                self.get_name(), names[0])

        event_data = {"objects": obj_data}
        Mgr.do("add_history", event_descr, event_data, update_time_id=False)

        Mgr.update_locally("texproj_prop", "on", False, self.get_id())

    def update_selection_state(self, is_selected=True):

        if not self._subobj_root:
            return

        self._subobj_root.set_color_scale(1. if is_selected else .1)

        if not self._is_on:
            return

        if is_selected:

            for target_id, target_data in self._targets.iteritems():

                model = Mgr.get("model", target_id)

                if model:
                    uv_set_ids = target_data["uv_set_ids"]
                    toplvl = target_data["toplvl"]
                    show_poly_sel = target_data["show_poly_sel"]
                    target = model.get_geom_object().get_geom_data_object()
                    target.project_uvs(uv_set_ids, projector=self._lens_np, toplvl=toplvl,
                                       show_poly_sel=show_poly_sel)

        else:

            for target_id, target_data in self._targets.iteritems():

                model = Mgr.get("model", target_id)

                if model:
                    uv_set_ids = target_data["uv_set_ids"]
                    toplvl = target_data["toplvl"]
                    target = model.get_geom_object().get_geom_data_object()
                    target.project_uvs(uv_set_ids, False, toplvl=toplvl)

    def is_valid(self):

        return self._size > .001

    def finalize(self):

        pass

    def show(self, *args, **kwargs):

        self.get_origin().show(*args, **kwargs)

    def hide(self, *args, **kwargs):

        self.get_origin().hide(*args, **kwargs)


MainObjects.add_class(TexProjectorManager)
MainObjects.add_class(TexProjectorEdgeManager)