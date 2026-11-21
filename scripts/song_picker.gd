extends PanelContainer
signal song_selected(result: Dictionary)
signal demo_selected
signal dismissed
const Library = preload("res://scripts/song_library.gd")
const Job = preload("res://scripts/import_job.gd")
var library := Library.new()
var entries: Array[Dictionary] = []
var list := ItemList.new()
var status := Label.new()
var difficulty := OptionButton.new()
var override_tempo := CheckButton.new()
var bpm := SpinBox.new()
var progress := ProgressBar.new()
var dialog := FileDialog.new()
var import_button: Button
var use_button: Button
var demo_button: Button
var close_button: Button
var cancel_button: Button
var job: RefCounted

func _ready() -> void:
	position = Vector2(65, 110)
	size = Vector2(1150, 535)
	var style := StyleBoxFlat.new()
	style.bg_color = Color("142131")
	style.set_corner_radius_all(18)
	style.content_margin_left = 24
	style.content_margin_right = 24
	style.content_margin_top = 18
	style.content_margin_bottom = 18
	add_theme_stylebox_override("panel", style)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 10)
	add_child(column)
	var heading := HBoxContainer.new()
	column.add_child(heading)
	var title := Label.new()
	title.text = "YOUR MUSIC / LOCAL SONG LIBRARY"
	title.add_theme_font_size_override("font_size", 24)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	heading.add_child(title)
	close_button = _button(heading, "BACK", func(): dismissed.emit())
	var hint := Label.new()
	hint.text = "Import MP3, WAV or Ogg Vorbis. Audio stays on this device. 8 sec–10 min / up to 64 MiB."
	column.add_child(hint)
	list.custom_minimum_size = Vector2(1080, 140)
	list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	list.item_selected.connect(func(_index: int): _describe_selection())
	column.add_child(list)
	var options := HBoxContainer.new()
	options.add_theme_constant_override("separation", 16)
	column.add_child(options)
	var levels := {"easy": "more recovery", "normal": "jab + hook", "hard": "longer runs", "expert": "sustained beats"}
	for level in levels:
		difficulty.add_item("%s / %s" % [str(level).capitalize(), levels[level]])
		difficulty.set_item_metadata(difficulty.item_count - 1, level)
	difficulty.select(1)
	options.add_child(difficulty)
	override_tempo.text = "Correct BPM manually"
	options.add_child(override_tempo)
	bpm.min_value = 60
	bpm.max_value = 180
	bpm.value = 120
	bpm.editable = false
	override_tempo.toggled.connect(func(on: bool): bpm.editable = on)
	options.add_child(bpm)
	status.text = "Choose a song or import one to arrange it automatically."
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status.custom_minimum_size.y = 40
	column.add_child(status)
	progress.show_percentage = true
	progress.custom_minimum_size.y = 12
	column.add_child(progress)
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 18)
	column.add_child(actions)
	import_button = _button(actions, "IMPORT SONG…", func(): dialog.popup_centered_ratio(0.8))
	use_button = _button(actions, "PREPARE SELECTED SONG", _prepare_selected)
	demo_button = _button(actions, "USE DEMO LOOP", func(): demo_selected.emit())
	cancel_button = _button(actions, "CANCEL ANALYSIS", func():
		if job:
			job.cancel()
			status.text = "Cancelling…")
	cancel_button.visible = false
	dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	dialog.access = FileDialog.ACCESS_FILESYSTEM
	dialog.filters = PackedStringArray(["*.mp3,*.wav,*.ogg;Audio files", "*.mp3;MP3", "*.wav;WAV", "*.ogg;Ogg Vorbis"])
	dialog.title = "Import a local song"
	dialog.use_native_dialog = true
	dialog.file_selected.connect(begin_import)
	add_child(dialog)
	refresh()

func _button(parent: Node, title: String, callback: Callable) -> Button:
	var button := Button.new()
	button.text = title
	button.custom_minimum_size.y = 42
	button.pressed.connect(callback)
	parent.add_child(button)
	return button

func refresh() -> void:
	entries = library.songs()
	list.clear()
	for song in entries:
		list.add_item("%s    ·    %d:%02d" % [song.title, int(song.duration) / 60, int(song.duration) % 60])
	use_button.disabled = entries.is_empty()

func _describe_selection() -> void:
	if job or list.get_selected_items().is_empty():
		return
	status.text = "Choose intensity, then prepare. Existing charts are reused; different settings create a separate chart."

func _prepare_selected() -> void:
	var indexes := list.get_selected_items()
	if not indexes.is_empty():
		begin_import(library.audio_path(entries[indexes[0]]))
	else:
		status.text = "Select a song from the list first."

func begin_import(path: String) -> void:
	if job:
		return
	job = Job.new()
	var error: Error = job.start(path, difficulty.get_selected_metadata(),
		float(bpm.value) if override_tempo.button_pressed else 0.0, library.root_path)
	if error != OK:
		job = null
		status.text = "Could not start audio analysis. Try again."
		return
	status.text = "Decoding and arranging locally…"
	_busy(true)

func _busy(value: bool) -> void:
	for button in [import_button, use_button, demo_button, close_button, difficulty, override_tempo]:
		button.disabled = value
	list.mouse_filter = Control.MOUSE_FILTER_IGNORE if value else Control.MOUSE_FILTER_STOP
	bpm.editable = not value and override_tempo.button_pressed
	cancel_button.visible = value

func _process(_delta: float) -> void:
	if not job:
		return
	progress.value = job.fraction() * 100.0
	if job.thread.is_alive():
		return
	var was_cancelled: bool = job.cancelled
	var result: Dictionary = job.finish()
	job = null
	_busy(false)
	refresh()
	if was_cancelled:
		status.text = "Cancelled. Your current song is unchanged."
	elif result.has("error"):
		status.text = result.error
	else:
		progress.value = 100
		status.text = "Ready. The chart is saved for repeat play."
		song_selected.emit(result)

func _exit_tree() -> void:
	if job:
		job.cancel()
		job.finish()
		job = null
