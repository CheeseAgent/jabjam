extends SceneTree
## Cross-renderer regression probe. Input and output are temporary files supplied by the test.
const Coach = preload("res://scripts/coach.gd")

func _initialize() -> void:
	call_deferred("_sample")

func _sample() -> void:
	var args := OS.get_cmdline_user_args()
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var coach := Coach.new()
	root.add_child(coach)
	coach.set_chart(fixture.notes)
	var frames := []
	for t: float in fixture.times:
		coach.seek(t)
		var world := {}
		for id: String in coach.rig.joints:
			var joint: Node2D = coach.rig.joints[id]
			# Stage coordinates; the host fits its own display rectangle separately.
			var xf: Transform2D = joint.transform
			var parent := joint.get_parent()
			while parent != coach.rig:
				xf = parent.transform * xf
				parent = parent.get_parent()
			world[id] = [xf.origin.x, xf.origin.y, xf.get_rotation(), xf.get_scale().x]
		var zooms := {}
		var fronts := {}
		for id: String in coach.rig.artwork:
			zooms[id] = coach.rig.artwork[id].scale.x
		for id: String in coach.rig.front_panels:
			var panel: Sprite2D = coach.rig.front_panels[id]
			if panel.visible:
				fronts[id] = [panel.position.x, panel.position.y, panel.scale.x, panel.z_index]
		var yaw := {}
		for id: String in coach.rig.surfaces:
			yaw[id] = coach.rig.surfaces[id].get_shader_parameter("yaw")
		frames.append({"pose": coach.pose_at(t), "world": world, "zooms": zooms, "fronts": fronts,
				"yaw": yaw, "face": coach.rig.faces.find_key(coach.rig.face_sprite.texture)})
	var out := FileAccess.open(args[1], FileAccess.WRITE)
	out.store_string(JSON.stringify(frames, "", true, true))
	out.close()
	coach.free()
	quit()
