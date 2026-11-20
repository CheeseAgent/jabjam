extends Control
## Adapter from the existing session's absolute song clock to the shared cutout clips.
const Rig = preload("res://scenes/milktea_rig.tscn")
var rig = Rig.instantiate()
var timing: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/coaches/timing.json"))
var times := PackedFloat64Array()
var actions := PackedStringArray()

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
	for note: Dictionary in notes:
		times.append(note.time)
		actions.append(note.action)

func seek(t: float) -> void:
	var pose := pose_at(t)
	rig.apply_pose(pose[0], pose[1], pose[2])

func pose_at(t: float) -> Array:
	# The same half-open boundaries as video/coach_timeline.py. No accumulating timer.
	var i := times.bsearch(t, false)
	var elapsed := t - times[i-1] if i > 0 else INF
	if i < times.size():
		var until_hit := times[i] - t
		if until_hit > 0 and until_hit <= float(timing.prepare) and elapsed >= float(timing.minimum_landing):
			return ["prepare", actions[i], 1.0 - until_hit / float(timing.prepare)]
	if i > 0:
		if elapsed < float(timing.strike):
			return ["strike", actions[i-1], elapsed / float(timing.strike)]
		var recovery_end := float(timing.strike) + float(timing.recover)
		if elapsed < recovery_end:
			return ["recover", actions[i-1], (elapsed - float(timing.strike)) / float(timing.recover)]
		if i == times.size():
			var phase := (elapsed - float(timing.strike) - float(timing.recover)) / float(timing.celebrate)
			if phase >= 0.0 and phase < 1.0:
				return ["celebrate", "", phase]
	return ["idle", "", fmod(t, float(timing.idle)) / float(timing.idle)]
