extends RefCounted
const Generator = preload("res://scripts/chart_generator.gd")
const Library = preload("res://scripts/song_library.gd")
const Session = preload("res://scripts/session.gd")
const Job = preload("res://scripts/import_job.gd")

static func fixture(bpm := 120.0, silent := false) -> AudioStreamWAV:
	var stream := AudioStreamWAV.new()
	stream.mix_rate = 16000
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	var bytes := PackedByteArray()
	bytes.resize(24 * 16000 * 2)
	for index in range(24 * 16000):
		var time := float(index) / 16000
		var beat := fmod(time, 60.0 / bpm)
		var amplitude := 0.0 if silent or (time >= 8 and time < 12) else (0.18 if time < 8 else 0.8)
		var value := amplitude * exp(-beat * 40) * sin(TAU * 220 * time)
		bytes.encode_s16(index * 2, int(value * 32767))
	stream.data = bytes
	return stream

static func run(tree: SceneTree, check: Callable) -> void:
	var source := fixture()
	var analysis := Generator.analyze(source)
	check.call(not analysis.has("error"), "PCM audio can be analyzed offline")
	if analysis.has("error"):
		return
	print("Detected fixture tempo: ", analysis.estimated_bpm, " / confidence: ", analysis.confidence)
	check.call(absf(analysis.estimated_bpm - 120) < 3, "120 BPM pulse fixture estimates near 120 BPM")
	var slower := Generator.analyze(fixture(100.0))
	check.call(absf(slower.estimated_bpm - 100) < 3, "100 BPM fixture produces a different tempo estimate")
	var id := "a".repeat(64)
	var chart := Generator.generate(analysis, id, 24.0)
	check.call(not chart.has("error") and Generator.valid(chart, id, 24.0), "Generated chart validates")
	if chart.has("error"):
		return
	check.call(chart == Generator.generate(analysis, id, 24.0), "Identical audio and settings reproduce the chart")
	var easy := Generator.generate(analysis, id, 24.0, "easy")
	check.call(easy.id != chart.id and easy.notes.size() <= chart.notes.size(), "Easy has its own identity and no greater density")
	var corrected := Generator.generate(analysis, id, 24.0, "normal", 100.0)
	check.call(corrected.id != chart.id and corrected.bpm == 100, "Manual BPM changes both grid and chart identity")
	var safe := true
	var quiet_count := 0
	var loud_count := 0
	for i in range(chart.notes.size()):
		var note: Dictionary = chart.notes[i]
		if note.time >= 8.2 and note.time < 11.8:
			safe = false
		if i > 0:
			var previous: Dictionary = chart.notes[i - 1]
			if note.time - previous.time < 0.429 or str(note.action).begins_with("left") == str(previous.action).begins_with("left"):
				safe = false
			if str(previous.action).ends_with("hook") and note.time - previous.time < 0.899:
				safe = false
		if note.time < 8:
			quiet_count += 1
		if note.time >= 16 and note.time < 21:
			loud_count += 1
	check.call(safe, "Notes alternate hands, allow recovery and skip silence")
	var actions: Array = chart.notes.map(func(note: Dictionary) -> String: return note.action)
	check.call("left_hook" in actions and "right_hook" in actions, "Normal arrangement includes hooks from both hands")
	check.call(loud_count > quiet_count * 2, "Loud phrase has more than double the quiet phrase cue density")
	var on_grid := true
	for note in chart.notes:
		if absf(note.time - roundf(note.time / 0.5) * 0.5) > 0.08:
			on_grid = false
	check.call(on_grid, "Synthetic pulse cues stay within 80ms of the true beat")
	check.call(Generator.analyze(fixture(120.0, true)).has("error"), "Silent input is rejected")
	var root_path := "user://import-tests"
	DirAccess.make_dir_recursive_absolute(root_path)
	var source_path := root_path.path_join("song.wav")
	source.save_to_wav(source_path)
	var library := Library.new(root_path.path_join("library"))
	var imported := library.import_song(source_path)
	check.call(not imported.has("error"), "Runtime WAV import creates audio and chart")
	if imported.has("error"):
		print(imported)
		return
	check.call(library.songs().size() == 1, "Imported song appears in local library")
	var cached := library.import_song(source_path, "normal", 0.0, func(f: float) -> bool: return f == 0.0 or f == 1.0)
	check.call(not cached.has("error") and cached.chart == imported.chart, "Reimport reuses a saved chart without analysis")
	var renamed := root_path.path_join("renamed.wav")
	DirAccess.copy_absolute(source_path, renamed)
	var duplicate := library.import_song(renamed)
	check.call(duplicate.song.id == imported.song.id and library.songs().size() == 1, "File rename deduplicates by content hash")
	DirAccess.remove_absolute(source_path)
	var reopened := Library.new(library.root_path).import_song(library.audio_path(imported.song))
	check.call(not reopened.has("error") and reopened.chart.id == imported.chart.id, "Local copy survives original removal and library restart")
	var chart_path := library.root_path.path_join(imported.song.id).path_join(imported.chart.id + ".json")
	Library.write_json(chart_path, {"broken": true})
	var repaired := library.import_song(library.audio_path(imported.song))
	check.call(not repaired.has("error") and repaired.chart == imported.chart, "Invalid chart cache regenerates deterministically")
	check.call(library.import_song("missing.flac").has("error"), "Unsupported format gives a recoverable error")
	check.call(library.import_song("missing.mp3").has("error"), "Missing source gives a recoverable error")
	var bad := FileAccess.open(root_path.path_join("invalid.mp3"), FileAccess.WRITE)
	bad.store_string("not an audio file".repeat(3))
	bad.close()
	check.call(library.import_song(root_path.path_join("invalid.mp3")).has("error"), "Invalid content is rejected")
	for extension in ["mp3", "ogg"]:
		var decoded := library.import_song("res://tests/fixtures/pulse." + extension)
		check.call(not decoded.has("error"), "Runtime " + extension + " decoder and arrangement")
		if not decoded.has("error"):
			check.call(absf(decoded.chart.bpm - 120) < 4 and absf(decoded.song.duration - 24) < 0.5,
				"Compressed " + extension + " maintains timing and tempo")
	var s := Session.new()
	s.start(imported.chart)
	for note in s.chart:
		s.punch(note.action, note.time)
	s.advance(imported.song.duration)
	check.call(s.state == Session.State.STAMP and s.hits == s.chart.size(), "Imported chart plays through its actual duration")
	check.call(s.result().chart_id == imported.chart.id and s.result().song_id == imported.song.id,
		"Practice history is scoped to song and chart version")
	var job := Job.new()
	job.cancel()
	job.start(renamed, "normal", 0.0, root_path.path_join("cancelled-library"))
	while job.thread.is_alive():
		await tree.process_frame
	check.call(job.finish().has("error") and not DirAccess.dir_exists_absolute(root_path.path_join("cancelled-library")),
		"Cancelled import leaves no song entry")
	# Real picker worker -> selected song -> main scene -> dynamic result screen.
	var app := preload("res://scenes/main.tscn").instantiate()
	tree.root.add_child(app)
	await tree.process_frame
	app.picker.library = library
	app._open_library()
	app._primary()
	check.call(app.session.state == Session.State.READY, "Library modal blocks gameplay shortcuts")
	app.picker.begin_import(renamed)
	var deadline := Time.get_ticks_msec() + 10000
	while app.picker.job and Time.get_ticks_msec() < deadline:
		await tree.process_frame
	check.call(app.picker.job == null and app.selected_song.id == imported.song.id and not app.picker.visible,
		"Background import selects the song and returns to home")
	app._start()
	check.call(app.session.duration == imported.song.duration and app.player.stream.get_length() == imported.song.duration,
		"Selected audio and chart start together")
	app.player.seek(imported.song.duration - 0.1)
	await tree.create_timer(0.35).timeout
	check.call(app.session.state == Session.State.STAMP, "Imported song finishes without hanging at EOF")
	app._select_demo()
	app._start()
	check.call(app.session.chart.size() == 32 and app.session.duration == 36, "Demo remains playable after custom music")
	app.player.stop()
	app.player.stream = null
	await tree.create_timer(0.15).timeout
	app.queue_free()
	await tree.process_frame
