extends SceneTree

const Session = preload("res://scripts/session.gd")
const Store = preload("res://scripts/practice_store.gd")
const Main = preload("res://scenes/main.tscn")
var failures := 0
var checks := 0

func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(message)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var s := Session.new()
	s.start()
	var original := s.chart.duplicate(true)
	check(s.punch("left_jab", 4.0) == "PERFECT", "Exact matching note must hit")
	check(s.punch("left_jab", 5.0) == "WRONG MOVE", "Wrong hand cannot score")
	check(s.score == 100 and s.combo == 0 and s.misses == 1, "Wrong move consumes the note and resets combo")
	check(s.punch("left_jab", 6.14) == "GOOD", "Outer timing window scores GOOD")
	s.advance(10.5)
	check(s.misses == 5, "All overdue notes must miss after a frame stall")
	var frozen: float = s.clock
	s.toggle_pause()
	s.advance(20.0)
	check(s.clock == frozen, "Paused timeline cannot advance")
	check(s.punch("right_jab", 20.0) == "IGNORED", "Paused input cannot score")
	s.toggle_pause()
	s.advance(9.0)
	check(s.clock == frozen, "Audio jitter must not rewind the clock")
	s.start()
	check(s.chart == original and s.attempts == 0 and s.score == 0, "Restart resets state and reproduces the chart")
	check(s.punch("left_jab", 0.0) == "EARLY" and s.cursor == 0, "Early input cannot consume upcoming notes")
	check(s.punch("invalid", 4.0) == "IGNORED", "Unknown action cannot change scoring")
	s.start()
	for note in s.chart:
		s.punch(note.action, note.time)
	check(s.score == 3200 and s.best_combo == 32 and s.misses == 0, "A perfect simulated run scores all 32 notes")
	s.advance(36.0)
	check(s.state == Session.State.STAMP, "Completed song waits for a deliberate stamp")
	check(s.stamp() and not s.stamp(), "Stamp must be accepted only once")
	check(s.result().mode == "simulation" and not s.result().has("full_combo"), "Simulated play is never an official exercise record")
	var path := "user://test_history.json"
	DirAccess.remove_absolute(path)
	check(Store.save_result(s.result(), path) == OK, "Practice result persists")
	check(Store.read_history(path).size() == 1, "Persisted practice can be read back")
	check(Store.save_result({"mode": "verified"}, path) == ERR_INVALID_DATA, "Practice store rejects non-simulation data")
	var corrupt := FileAccess.open(path, FileAccess.WRITE)
	corrupt.store_string("broken json")
	corrupt.close()
	check(Store.read_history(path).is_empty(), "Corrupt history must not crash startup")
	DirAccess.remove_absolute(path)
	# Integration: instantiate the real scene, dispatch physical keyboard events,
	# and exercise pause/restart/end UI transitions without requiring a display.
	var app := Main.instantiate()
	root.add_child(app)
	await process_frame
	check(app.primary_button.visible and not app.pause_button.visible, "Home screen controls")
	var start := InputEventKey.new()
	start.physical_keycode = KEY_SPACE
	start.pressed = true
	Input.parse_input_event(start)
	await process_frame
	check(app.session.state == Session.State.PLAYING and app.player.playing, "Space starts scene and audio")
	await create_timer(0.15).timeout
	check(app.session.clock > 0.0, "Audio master clock advances during playback")
	app._pause()
	check(app.session.state == Session.State.PAUSED and app.player.stream_paused, "Scene pauses audio with rules")
	app._restart()
	check(app.session.state == Session.State.PLAYING and not app.player.stream_paused, "Restart from pause resumes new track")
	app.player.seek(35.9)
	await create_timer(0.35).timeout
	check(app.session.state == Session.State.STAMP and not app.player.playing, "Audio timeline automatically completes training")
	check(app.primary_button.visible and app.primary_button.text.begins_with("STAMP"), "End screen exposes stamp action")
	# Avoid writing fake training results into the user's normal history.
	app.session.stamp()
	app._sync_ui()
	check(app.primary_button.text.begins_with("PLAY AGAIN") and not app.coach.visible, "Results screen controls")
	app.player.stop()
	app.player.stream = null
	# Let the audio mixer release stopped playbacks before shutting down.
	await create_timer(0.1).timeout
	app.queue_free()
	await process_frame
	await preload("res://tests/test_song_import.gd").run(self, check)
	print("JabJam: %d checks, %d failures" % [checks, failures])
	quit(0 if failures == 0 else 1)
