extends Node
## Development adapter. Hardware adapters can expose the same punch signal later.
signal punch(action: String)
signal primary
signal pause_requested
signal restart_requested

const KEYS := {KEY_F: "left_jab", KEY_J: "right_jab", KEY_D: "left_hook", KEY_K: "right_hook"}

func _unhandled_key_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	var key: int = event.physical_keycode
	if key in KEYS:
		punch.emit(KEYS[key])
	elif key == KEY_SPACE:
		primary.emit()
	elif key == KEY_ESCAPE:
		pause_requested.emit()
	elif key == KEY_R:
		restart_requested.emit()
	else:
		return
	get_viewport().set_input_as_handled()
