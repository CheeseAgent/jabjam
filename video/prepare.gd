extends SceneTree
## Runs in a temporary XDG directory, independent of the interactive scene.
const Library = preload("res://scripts/song_library.gd")
const Demo = preload("res://scripts/demo_audio.gd")

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 6:
		printerr("Expected audio source, demo path, mode, difficulty, BPM and chart path.")
		quit(2)
		return
	var audio := args[0]
	if audio == "builtin:demo":
		audio = args[1]
		if Demo.create_stream().save_to_wav(audio) != OK:
			printerr("Cannot write demo audio.")
			quit(1)
			return
	if args[2] == "auto":
		var result := Library.new().import_song(audio, args[3], float(args[4]))
		if result.has("error"):
			printerr(result.error)
			quit(1)
			return
		if Library.write_json(args[5], result.chart) != OK:
			printerr("Cannot write action chart.")
			quit(1)
			return
	quit()
