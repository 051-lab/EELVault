# Changelog

All notable changes to STILLROOM.

## [0.1.0] — 2026-08-14
### Added
- v0.1.0 "Nearfield Depth" — compact spatial ambience processor for RootlessJamesDSP / JDSP4Linux.
- Four native EEL2 sliders: Space (42), Depth (36), Wet (24), Tone (56) with sequential declarations.
- M/S encode/decode architecture with mathematically untouched direct mid/side path.
- Six asymmetric short-tap early reflection ring establishing walls and distance.
- Depth air-absorption filter: frequency-dependent recession that reduces upper-frequency reflection energy and shifts the direct/reflected balance.
- Five-stage damped allpass diffuser (delays ~0.65/1.0/1.5/2.2/3.2 ms) supplying diffuse continuity — not a recognizable reverb tail.
- Side-only spatial injection with opposed-polarity cancellation: the spatial field is injected as side energy that cancels under mono summing, preserving mono-safe playback without comb-filtering.
- Wet internally capped to a ~0.0–0.35 spatial-send range to protect headroom and long-session listenability.
- Independent allpass feedback caps (no global feedback loop); diffuse output constrained to 25–40% of generated spatial energy, always subordinate to the early field.
- Parameter smoothing on all controls (especially Space) to prevent zippering from retuned delays.
- Denormal dither, non-finite input sanitizer, sample-path slider fallback bridge.
- README, metadata.json, CHANGELOG, archived byte-identical `versions/v0.1.0-nearfield-depth.eel`.

### Design principles
- Dry signal remains the anchor: direct-path clarity preserved, no pre-delay or reverb bloom.
- Spaciousness derived from decorrelated side energy; mid path phase-coherent.
- No saturation, no FFT/FIR, no large delay buffers, no oversampling.
