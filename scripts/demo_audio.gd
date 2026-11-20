extends RefCounted
## Original synthesized practice loop; no external music or assets required.

static func create_stream() -> AudioStreamWAV:
	var rate := 22050
	var duration := 37.0
	var bytes := PackedByteArray()
	bytes.resize(int(duration * rate) * 2)
	var notes := [130.81, 155.56, 174.61, 116.54]
	for i in range(int(duration * rate)):
		var t := float(i) / rate
		var beat := fmod(t, 0.5)
		var eighth := fmod(t, 0.25)
		var bass: float = notes[int(t / 4.0) % notes.size()]
		var kick := sin(TAU * (48.0 * beat + 2.0 * (1.0 - exp(-beat * 30.0)))) * exp(-beat * 18.0)
		var hat := sin(TAU * 7300.0 * t) * exp(-eighth * 100.0)
		var tone := sin(TAU * bass * t) * exp(-beat * 5.0)
		# Audible contrast for testing the dynamic chart: intro, verse, peak, bridge, finale.
		var intensity := 0.36 if t < 8.0 else (0.62 if t < 16.0 else (1.0 if t < 28.0 else (0.24 if t < 33.0 else 0.86)))
		var fade := minf(1.0, maxf(0.0, duration - t))
		var value := (kick * 0.38 + hat * 0.07 + tone * 0.15) * intensity * fade
		bytes.encode_s16(i * 2, int(clampf(value, -1.0, 1.0) * 32767.0))
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = rate
	stream.stereo = false
	stream.data = bytes
	return stream
