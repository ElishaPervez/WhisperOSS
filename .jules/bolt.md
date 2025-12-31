## 2024-05-22 - Audio Visualizer Optimization
**Learning:** For audio visualizers, Peak Amplitude (`np.max(np.abs(int16_array))`) provides a ~2x performance boost over standard RMS (`np.sqrt(np.mean(float64_array**2))`) while offering a snappier visual response that is often preferred.
**Action:** When accurate energy measurement isn't strictly required (e.g., UI animations), prefer Peak Amplitude or Mean Absolute Value over full RMS to save CPU cycles on the audio thread.
