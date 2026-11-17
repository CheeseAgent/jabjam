extends Control

const Session = preload("res://scripts/session.gd")
const DemoAudio = preload("res://scripts/demo_audio.gd")
const Store = preload("res://scripts/practice_store.gd")
const InputAdapter = preload("res://scripts/simulated_input.gd")
const Coach = preload("res://scripts/coach.gd")
const MINT := Color("72efc0")
const CORAL := Color("ff947f")
const WHITE := Color("edf3fa")
const MUTED := Color("95a7bd")
const LANES := ["left_hook", "left_jab", "right_jab", "right_hook"]
const NAMES := ["L HOOK", "L JAB", "R JAB", "R HOOK"]
const KEYS := ["D", "F", "J", "K"]

var session := Session.new()
var player := AudioStreamPlayer.new()
var input_adapter := InputAdapter.new()
var coach := Coach.new()
var primary_button: Button
var pause_button: Button
var restart_button: Button
var strike_buttons: Array[Button] = []
var font := ThemeDB.fallback_font
var flash := 0.0
var feedback := ""
var demonstrated_note := -1
var save_notice := ""
var history_count := 0

func _ready() -> void:
	add_child(player)
	player.stream = DemoAudio.create_stream()
	player.volume_db = -5.0
	add_child(input_adapter)
	input_adapter.punch.connect(_punch)
	input_adapter.primary.connect(_primary)
	input_adapter.pause_requested.connect(_pause)
	input_adapter.restart_requested.connect(_restart)
	coach.position = Vector2(890, 205)
	coach.size = Vector2(300, 310)
	add_child(coach)
	primary_button = _button("START PRACTICE   /   SPACE", Rect2(80, 570, 410, 58), _primary, MINT)
	pause_button = _button("PAUSE / ESC", Rect2(900, 570, 145, 48), _pause)
	restart_button = _button("RESTART / R", Rect2(1060, 570, 145, 48), _restart)
	for i in range(4):
		var action: String = LANES[i]
		strike_buttons.append(_button(KEYS[i] + "   " + NAMES[i], Rect2(80 + i * 190, 570, 176, 58),
			_punch.bind(action), MINT if i < 2 else CORAL))
	history_count = Store.read_history().size()
	_sync_ui()

func _button(title: String, rect: Rect2, callback: Callable, color := Color("25364b")) -> Button:
	var button := Button.new()
	button.text = title
	button.position = rect.position
	button.size = rect.size
	button.focus_mode = Control.FOCUS_NONE
	button.add_theme_font_size_override("font_size", 17)
	button.add_theme_color_override("font_color", Color("0b1521") if color == MINT or color == CORAL else WHITE)
	for style in ["normal", "hover", "pressed"]:
		var box := StyleBoxFlat.new()
		box.bg_color = color.lightened(0.1) if style == "hover" else color
		if style == "pressed":
			box.bg_color = color.darkened(0.2)
		box.set_corner_radius_all(12)
		button.add_theme_stylebox_override(style, box)
	button.pressed.connect(callback)
	add_child(button)
	return button

func _audio_time() -> float:
	# Audio is the master clock. Clamp at the session layer to absorb mix jitter.
	return maxf(0.0, player.get_playback_position() + AudioServer.get_time_since_last_mix() - AudioServer.get_output_latency())

func _start() -> void:
	session.start()
	player.stream_paused = false
	player.play()
	demonstrated_note = -1
	save_notice = ""
	feedback = "GET READY"
	flash = 1.0
	_sync_ui()

func _primary() -> void:
	match session.state:
		Session.State.READY, Session.State.RESULTS:
			_start()
		Session.State.STAMP:
			_stamp()
		Session.State.PLAYING, Session.State.PAUSED:
			_pause()

func _pause() -> void:
	if session.state not in [Session.State.PLAYING, Session.State.PAUSED]:
		return
	session.toggle_pause()
	player.stream_paused = session.state == Session.State.PAUSED
	_sync_ui()

func _restart() -> void:
	_start()

func _punch(action: String) -> void:
	if session.state == Session.State.STAMP:
		_stamp()
		return
	if session.state != Session.State.PLAYING:
		return
	feedback = session.punch(action, _audio_time())
	flash = 1.0
	_sync_ui()

func _stamp() -> void:
	if not session.stamp():
		return
	var error := Store.save_result(session.result())
	save_notice = "Saved locally to practice history." if error == OK else "Could not save practice history (%s)." % error_string(error)
	history_count = Store.read_history().size()
	_sync_ui()

func _process(delta: float) -> void:
	flash = maxf(0.0, flash - delta * 1.8)
	if session.state == Session.State.PLAYING:
		var old_misses: int = session.misses
		session.advance(_audio_time())
		if session.misses > old_misses:
			feedback = "MISS"
			flash = 1.0
		# Demonstrate before the target reaches the hit line.
		if session.cursor < session.chart.size():
			var note: Dictionary = session.chart[session.cursor]
			if float(note.time) - session.clock <= 0.5 and demonstrated_note != session.cursor:
				coach.demonstrate(note.action)
				demonstrated_note = session.cursor
		if session.state == Session.State.STAMP:
			player.stop()
			_sync_ui()
	queue_redraw()

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT and session.state == Session.State.PLAYING:
		_pause()

func _sync_ui() -> void:
	var playing: bool = session.state in [Session.State.PLAYING, Session.State.PAUSED]
	if not playing:
		player.stop()
	coach.visible = session.state in [Session.State.READY, Session.State.PLAYING]
	coach.process_mode = Node.PROCESS_MODE_INHERIT if coach.visible else Node.PROCESS_MODE_DISABLED
	pause_button.visible = playing
	pause_button.text = "RESUME / ESC" if session.state == Session.State.PAUSED else "PAUSE / ESC"
	restart_button.visible = playing
	primary_button.visible = not playing or session.state == Session.State.PAUSED
	primary_button.text = "START PRACTICE   /   SPACE"
	if session.state == Session.State.PAUSED:
		primary_button.text = "RESUME   /   SPACE"
	elif session.state == Session.State.STAMP:
		primary_button.text = "STAMP IT!   /   SPACE OR PUNCH"
	elif session.state == Session.State.RESULTS:
		primary_button.text = "PLAY AGAIN   /   SPACE"
	for button in strike_buttons:
		button.visible = session.state == Session.State.PLAYING
	queue_redraw()

func _panel(rect: Rect2, color: Color, radius := 18) -> void:
	var box := StyleBoxFlat.new()
	box.bg_color = color
	box.set_corner_radius_all(radius)
	box.draw(get_canvas_item(), rect)

func _text(at: Vector2, value: String, size_px := 20, color := WHITE) -> void:
	draw_string(font, at, value, HORIZONTAL_ALIGNMENT_LEFT, -1, size_px, color)

func _draw() -> void:
	draw_rect(Rect2(0, 0, 1280, 720), Color("0a0f17"))
	draw_circle(Vector2(1190, -90), 320, Color("10272a"))
	_text(Vector2(80, 65), "JAB", 34, MINT)
	_text(Vector2(145, 65), "JAM", 34)
	_text(Vector2(280, 61), "MOVE TO YOUR OWN BEAT", 14, MUTED)
	_panel(Rect2(940, 34, 260, 38), Color("23342f"), 19)
	_text(Vector2(959, 59), "SIMULATED INPUT / PRACTICE", 14, MINT)
	draw_line(Vector2(80, 94), Vector2(1200, 94), Color("263344"))
	_text(Vector2(80, 681), "F / J  jab     D / K  hook     SPACE  start / pause     ESC  pause     R  restart", 16, MUTED)
	_text(Vector2(970, 681), "LOCAL  /  NO CAMERA", 15, MINT)
	match session.state:
		Session.State.READY:
			_draw_home()
		Session.State.PLAYING:
			_draw_training()
		Session.State.PAUSED:
			_text(Vector2(80, 235), "TAKE A BREATHER.", 54)
			_text(Vector2(84, 289), "Music and the chart are paused together.", 24, MUTED)
			_text(Vector2(84, 340), "Resume when you are ready.", 24, MINT)
		Session.State.STAMP:
			_text(Vector2(80, 225), "MAKE IT COUNT.", 60)
			_text(Vector2(84, 285), "Your practice is complete. One last punch to seal it.", 24, MUTED)
			_text(Vector2(84, 388), "36 SECONDS.  YOUR MOMENT.", 32, MINT)
		Session.State.RESULTS:
			_draw_results()

func _draw_home() -> void:
	_text(Vector2(80, 155), "01 / THE PRACTICE ROOM", 17, MINT)
	_text(Vector2(76, 235), "FIND YOUR", 66)
	_text(Vector2(76, 310), "FIGHTING RHYTHM.", 66)
	_text(Vector2(82, 363), "A small loop. Four moves. A fresh start.", 25, MUTED)
	_text(Vector2(82, 405), "Follow the lanes. Strike as each tile meets the line.", 21, MUTED)
	for i in range(3):
		_panel(Rect2(80 + i * 245, 449, 228, 76), Color("142131"), 12)
	_text(Vector2(98, 480), "36 SEC", 25)
	_text(Vector2(98, 506), "QUICK PRACTICE", 14, MUTED)
	_text(Vector2(343, 480), "120 BPM", 25)
	_text(Vector2(343, 506), "ORIGINAL DEMO LOOP", 14, MUTED)
	_text(Vector2(588, 480), "4 MOVES", 25)
	_text(Vector2(588, 506), "KEYBOARD OR TOUCH", 14, MUTED)
	_text(Vector2(910, 181), "YOUR CORNER", 17, MINT)
	_text(Vector2(903, 544), "Geometric coach / prototype", 16, MUTED)
	_text(Vector2(520, 605), "%d saved practices. No verified exercise scores." % history_count, 17, MUTED)

func _draw_training() -> void:
	_text(Vector2(80, 139), "DEMO LOOP / 120 BPM", 19, MINT)
	_text(Vector2(570, 139), "%02d / 36 SEC" % mini(36, int(session.clock)), 19, MUTED)
	_panel(Rect2(80, 163, 746, 370), Color("101b29"))
	for i in range(4):
		var x := 80.0 + i * 190
		if i > 0:
			draw_line(Vector2(x - 7, 180), Vector2(x - 7, 519), Color("253448"))
		_text(Vector2(x + 39, 200), NAMES[i], 16, MUTED)
		draw_line(Vector2(x + 10, 480), Vector2(x + 166, 480), MINT if i < 2 else CORAL, 4)
	for index in range(session.cursor, session.chart.size()):
		var note: Dictionary = session.chart[index]
		var y := 480.0 - (float(note.time) - session.clock) * 75.0
		if y < 235 or y > 510:
			continue
		var lane := LANES.find(note.action)
		var x := 100.0 + lane * 190
		var color := MINT if lane < 2 else CORAL
		_panel(Rect2(x, y - 23, 136, 46), color, 10)
		_text(Vector2(x + 53, y + 8), KEYS[lane], 25, Color("0b1521"))
	_text(Vector2(900, 145), "%04d" % session.score, 42)
	_text(Vector2(1050, 143), "%02d COMBO" % session.combo, 21, MINT)
	_text(Vector2(905, 191), "WATCH THE LINE. FEEL THE BEAT.", 14, MUTED)
	if flash > 0:
		_text(Vector2(905, 548), feedback, 25, MINT if feedback in ["PERFECT", "GOOD"] else CORAL)
	_panel(Rect2(80, 641, 1120, 4), Color("233042"), 2)
	_panel(Rect2(80, 641, 1120 * minf(session.clock / Session.DURATION, 1.0), 4), MINT, 2)

func _draw_results() -> void:
	_text(Vector2(80, 161), "PRACTICE STAMPED", 18, MINT)
	_text(Vector2(76, 245), "YOU SHOWED UP.", 66)
	_text(Vector2(82, 293), "Keep the rhythm. Come back for another round.", 24, MUTED)
	var values := [str(session.score), "%d / 32" % session.hits, str(session.best_combo)]
	var labels := ["PRACTICE POINTS", "MATCHED NOTES", "BEST COMBO"]
	for i in range(3):
		_panel(Rect2(80 + i * 375, 340, 350, 133), Color("142131"))
		_text(Vector2(102 + i * 375, 404), values[i], 45, MINT)
		_text(Vector2(102 + i * 375, 449), labels[i], 16, MUTED)
	_text(Vector2(82, 514), save_notice, 19, MUTED)
	_text(Vector2(520, 605), "Simulation only. No official Full Combo or fitness record.", 18, MUTED)
