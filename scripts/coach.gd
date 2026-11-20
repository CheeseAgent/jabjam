extends SubViewportContainer
## Original geometric stand-in, to be replaced with a rigged character later.
var left_arm: Node3D
var right_arm: Node3D
var body: Node3D
var motion: Tween
var elapsed := 0.0

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	stretch = true
	var viewport := SubViewport.new()
	viewport.size = Vector2i(310, 310)
	viewport.transparent_bg = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(viewport)
	var world := Node3D.new()
	viewport.add_child(world)
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("111d2a")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color.WHITE
	environment.environment.ambient_light_energy = 0.65
	world.add_child(environment)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-35, -25, 0)
	world.add_child(light)
	var camera := Camera3D.new()
	camera.position = Vector3(0, 1.4, 5)
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 3.6
	world.add_child(camera)
	body = Node3D.new()
	world.add_child(body)
	_part(body, Vector3(0, 1.35, 0), Vector3(0.8, 1, 0.45), Color("72efc0"))
	_part(body, Vector3(0, 2.2, 0), Vector3(0.58, 0.58, 0.58), Color("f5d6b8"), true)
	_part(body, Vector3(-0.24, 0.5, 0), Vector3(0.28, 0.85, 0.3), Color("60708b"))
	_part(body, Vector3(0.24, 0.5, 0), Vector3(0.28, 0.85, 0.3), Color("60708b"))
	left_arm = _arm(Vector3(-0.62, 1.5, 0.3), Color("72efc0"))
	right_arm = _arm(Vector3(0.62, 1.5, 0.3), Color("ff947f"))

func _part(parent: Node3D, at: Vector3, scale_by: Vector3, color: Color, sphere := false) -> void:
	var part := MeshInstance3D.new()
	part.mesh = SphereMesh.new() if sphere else BoxMesh.new()
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.8
	part.material_override = material
	part.position = at
	part.scale = scale_by
	parent.add_child(part)

func _arm(at: Vector3, color: Color) -> Node3D:
	var arm := Node3D.new()
	arm.position = at
	body.add_child(arm)
	_part(arm, Vector3.ZERO, Vector3(0.27, 0.55, 0.3), color)
	_part(arm, Vector3(0, 0.3, 0.15), Vector3(0.45, 0.45, 0.45), color, true)
	return arm

func demonstrate(action: String) -> void:
	if motion and motion.is_running():
		motion.kill()
	left_arm.rotation = Vector3.ZERO
	right_arm.rotation = Vector3.ZERO
	var arm := left_arm if action.begins_with("left") else right_arm
	var target := Vector3(-1.2, 0, 0)
	if action.ends_with("hook"):
		target = Vector3(-0.5, -0.9 if arm == left_arm else 0.9, 0)
	motion = create_tween()
	motion.tween_property(arm, "rotation", target, 0.12)
	motion.tween_property(arm, "rotation", Vector3.ZERO, 0.22)

func _process(delta: float) -> void:
	elapsed += delta
	if body:
		body.position.y = sin(elapsed * TAU * 2.0) * 0.025
