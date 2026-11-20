extends "res://scripts/coach.gd"
## F6 playback of all eight cues. Uses the same authored course and public audio as the MP4.
const COURSE := "res://courses/coach-demo.json"
var player := AudioStreamPlayer.new()

func _ready() -> void:
	super._ready()
	var course: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(COURSE))
	set_chart(course.actions)
	add_child(player)
	var music := COURSE.get_base_dir().path_join(str(course.course.music)).simplify_path()
	player.stream = AudioStreamOggVorbis.load_from_file(music)
	player.finished.connect(func(): seek(0.0))
	player.play()

func _process(_delta: float) -> void:
	if player.playing:
		var t := player.get_playback_position() + AudioServer.get_time_since_last_mix()
		seek(maxf(0.0, t - AudioServer.get_output_latency()))

func _exit_tree() -> void:
	player.stop()
	player.stream = null
