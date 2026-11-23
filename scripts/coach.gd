extends Control
## Adapter from the existing session's absolute song clock to the shared cutout clips.
const Rig = preload("res://scenes/milktea_rig.tscn")
var rig = Rig.instantiate()
var timing: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/coaches/timing.json"))
var times := PackedFloat64Array()
var actions := PackedStringArray()
var stances := PackedInt32Array([0])
var depths := PackedInt32Array([0])
@export_enum("left", "right") var lead_foot := "left"
var focus_starts := PackedFloat64Array()
var focus_ends := PackedFloat64Array()

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(rig)
	resized.connect(_fit)
	_fit()

func _fit() -> void:
	var factor := minf(size.x / rig.canvas_size.x, size.y / rig.canvas_size.y)
	rig.scale = Vector2.ONE * factor
	rig.position = (size - rig.canvas_size * factor) / 2.0

func set_chart(notes: Array) -> void:
	times.clear()
	actions.clear()
	stances = PackedInt32Array([0])
	depths = PackedInt32Array([0])
	focus_starts.clear()
	focus_ends.clear()
	for note: Dictionary in notes:
		times.append(note.time)
		actions.append(note.action)
		var step := 0
		if note.action == "step_left":
			step = -1
		elif note.action == "step_right":
			step = 1
		stances.append(clampi(stances[-1]+step, -1, 1))
		var depth_step := 1 if note.action == "step_forward" else (-1 if note.action == "step_backward" else 0)
		depths.append(clampi(depths[-1]+depth_step, -1, 1))
		if not str(note.action).begins_with("step_"):
			var face: Dictionary = timing.cutout.focus
			var start := maxf(0.0, float(note.time)-float(face.lead))
			var end := float(note.time)+float(face.hold)
			if not focus_ends.is_empty() and start <= focus_ends[-1]+float(face.merge_gap):
				focus_ends[focus_ends.size()-1] = end
			else:
				focus_starts.append(start)
				focus_ends.append(end)

func seek(t: float) -> void:
	var pose := pose_at(t)
	rig.apply_pose(pose[0], pose[1], pose[2], pose[3], pose[4], pose[5], lead_foot)

func pose_at(t: float) -> Array:
	# The same half-open boundaries as video/coach_timeline.py. No accumulating timer.
	var i := times.bsearch(t, false)
	var face_index := focus_starts.bsearch(t, false)-1
	var focused := face_index >= 0 and t < focus_ends[face_index]
	var prepare := float(timing.prepare)
	var strike := float(timing.strike)
	var recover := float(timing.recover)
	if i < times.size():
		var kind := "advance" if actions[i] == "step_forward" else ("retreat" if actions[i] == "step_backward" else ("step" if actions[i].begins_with("step_") else (actions[i] if actions[i] == "duck" else actions[i].get_slice("_", 1))))
		prepare = minf(float(timing.cutout.prepare[kind]), times[i])
	if i > 0 and actions[i-1].begins_with("step_"):
		recover = float(timing.cutout.step_recover)
	if i > 0 and i < times.size():
		var fit := minf(1.0, (times[i]-times[i-1]) / (strike+recover+prepare))
		prepare *= fit
		strike *= fit
		recover *= fit
	if i < times.size():
		var until_hit := times[i] - t
		if until_hit > 0 and until_hit <= prepare:
			return ["prepare", actions[i], 1.0 - until_hit/prepare, stances[i], focused, depths[i]]
	if i > 0:
		var elapsed := t - times[i-1]
		if elapsed < strike:
			return ["strike", actions[i-1], elapsed/strike, stances[i-1], focused, depths[i-1]]
		if elapsed < strike + recover:
			return ["recover", actions[i-1], (elapsed-strike)/recover, stances[i-1], focused, depths[i-1]]
		if i == times.size():
			var phase := (elapsed-strike-recover) / float(timing.celebrate)
			if phase >= 0.0 and phase < 1.0:
				return ["celebrate", "", phase, stances[i], focused, depths[i]]
	return ["idle", "", fmod(t, float(timing.idle)) / float(timing.idle), stances[i], focused, depths[i]]
