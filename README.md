# SP14 Emotion-Preserving AI Video Dubbing System

## Project Overview

When we watch a dubbed movie or video today, we often lose the "soul" of the original performance. Standard AI dubbing sounds robotic, while human dubbing replaces the original actor’s voice entirely. Our project, the Emotion-Preserving AI Video Dubbing System, creates a middle ground. We are building a tool that "listens" to the original speaker to learn two things: exactly what their voice sounds like and how they are feeling (the excitement, sadness, or anger in their tone). The system then translates their words into English and speaks them back using that same original voice, keeping the same emotional energy and timing.

---

## Team Members

- **Nishant Sai Challa** – nishantsaichalla@uvic.ca  
- **Dharun Kosanam** – dharunk@uvic.ca  
- **Ravi Vashi** – rvashi@uvic.ca  

---

## Problem Statement & Motivation

Global video content consumption continues to grow, yet language remains a significant accessibility barrier. Crucially, content creators face a major challenge in scaling their content: to reach a different language-speaking audience, they often have to sacrifice the unique voice and personality that allows them to connect with their viewers.

Existing dubbing approaches are insufficient for bridging this gap, suffering from one or more of the following limitations:

- **Disconnect with Audience:** Generic voices fail to carry the creator’s persona, making it difficult to build bond across languages.
- **Loss of Emotional Nuance:** The subtle affect and energy of the original performance are stripped away.
- **Loss of Speaker Identity:** The speaker's unique vocal characteristics are replaced entirely.
- **High Cost & Latency:** Professional dubbing is too expensive and slow for the fast-paced creator economy.

Automated text-to-speech dubbing fails to preserve prosody and affect, while professional dubbing replaces the original voice entirely. Our project aims to solve this by creating an identity and emotion-preserving speech-to-speech translation pipeline.

The system focuses on preserving:
1. **Who is speaking** (Voiceprint and Identity)
2. **How they feel** (Emotion, Energy, and Timing)
3. **What they say** (Accurate, Context-Aware Translation)

### Target Applications
- **User-Generated Media:** Enabling creators to connect natively with global audiences.
- Educational content and tutorials.
- Interviews and documentaries.
- Accessibility tools.
---

## System Architecture & Workflow

### 1. Input Phase
- User uploads a video file (MP4/MOV) via a React frontend.
- FastAPI backend receives the file.
- FFmpeg extracts the audio track.

### 2. Intelligence Phase (AI Loop)
- **Transcription:** OpenAI Whisper generates timestamped text.
- **Translation:** GPT-4o translates speech into English while preserving meaning and sentence length.
- **Vocal & Emotion Analysis:**
  - Speaker voice characteristics (“voiceprint”)
  - Emotional cues (pitch, speed, intensity, energy)

### 3. Synthesis Phase
- **Voice Cloning:** ElevenLabs generates English speech using the cloned voice of the original speaker.
- **Emotion Injection:** Emotional parameters are applied so the tone (joy, anger, sadness, etc.) matches the original delivery.

### 4. Assembly Phase
- FFmpeg time-stretches synthesized audio to match original timing.
- The new English audio replaces the original audio track.
- The final dubbed video is returned to the user for download and comparison.

---

## Technical Stack

### Frontend
- React 18+ & Vite
- Tailwind CSS

### Backend
- FastAPI (Python)
- Uvicorn
- FFmpeg

### AI & Cloud Services
- OpenAI Whisper (speech-to-text)
- AWS
- OpenAI GPT-4o (translation)
- ElevenLabs (voice cloning & speech synthesis)

---

## Tools, Datasets & Related Work

### Datasets
- **RAVDESS** – Emotional speech dataset for emotion recognition
- **ESD** – Multilingual emotional speech dataset
- **Mozilla Common Voice** – Large-scale multilingual speech corpus
- **Custom Test Corpus** – Curated real-world video clips

### Research Areas
- Speech Emotion Recognition (SER)
- Expressive Text-to-Speech (TTS)
- Voice Cloning & Speaker Embeddings
- Cross-lingual Speech Translation
- Prosody and Emotion Transfer

---

## Project Timeline

| Phase | Objectives |
|------|-----------|
| Weeks 1–2 | Literature review, dataset setup, audio extraction pipeline |
| Weeks 3–4 | Transcription and translation integration |
| Weeks 5–6 | Voice cloning and emotion analysis |
| Weeks 7–8 | End-to-end evaluation and refinement |
| Week 9 | Final report  and presentation |

---

## Individual Objectives & Performance Indicators

### Nishant Sai Challa

**Objective:** Core backend pipeline and AI integration  

- **PI1 (Basic):** Implement FFmpeg-based audio extraction  
- **PI2 (Basic):** Integrate Whisper transcription  
- **PI3 (Expected):** Integrate GPT-4o translation  
- **PI4 (Expected):** Implement FastAPI orchestration and error handling  
- **PI5 (Advanced):** Optimize pipeline latency via parallel processing  

---

### Dharun Kosanam

**Objective:** Emotion analysis and synthesis quality  

- **PI1 (Basic):** Extract pitch and energy features from speech  
- **PI2 (Basic):** Implement baseline TTS comparison  
- **PI3 (Expected):** Integrate emotion classification model  
- **PI4 (Expected):** Apply emotion-aware synthesis parameters  
- **PI5 (Advanced):** Quantitatively evaluate emotion preservation  

---

### Ravi Vashi

**Objective:** Frontend development, evaluation, and usability  

- **PI1 (Basic):** Build React-based video upload interface  
- **PI2 (Basic):** Implement video comparison player  
- **PI3 (Expected):** Visualize processing progress and pipeline stages  
- **PI4 (Expected):** Conduct user testing and collect feedback  
- **PI5 (Advanced):** Design evaluation dashboard for side-by-side comparison  

---
## References

1.  **Ericsson.** (2025). *Ericsson Mobility Report: November 2025*. Ericsson. [https://www.ericsson.com/4aca6f/assets/local/reports-papers/mobility-report/documents/2025/ericsson-mobility-report-november-2025.pdf](https://www.ericsson.com/4aca6f/assets/local/reports-papers/mobility-report/documents/2025/ericsson-mobility-report-november-2025.pdf)
2.  **Park, S., Park, S., You, T., & Yun, J.** (2025). Social links vs. language barriers: Decoding the global spread of streaming content. *Humanities and Social Sciences Communications*, 12, Article 76. [https://doi.org/10.1057/s41599-025-04400-2](https://doi.org/10.1057/s41599-025-04400-2)
3.  **Chaume, F.** (2007). Dubbing practices in Europe: Localisation beats globalisation. *Linguistica Antverpiensia, New Series – Themes in Translation Studies*, 6. [https://doi.org/10.52034/lanstts.v6i.188](https://doi.org/10.52034/lanstts.v6i.188)
4.  **Di Gangi, M., Rossenbach, N., Pérez, A., Bahar, P., Beck, E., Wilken, P., & Matusov, E.** (2022). Automatic video dubbing at AppTek. In *Proceedings of the 23rd Annual Conference of the European Association for Machine Translation (EAMT 2022)* (pp. 351–352). European Association for Machine Translation. [https://aclanthology.org/2022.eamt-1.65/](https://aclanthology.org/2022.eamt-1.65/)
5.  **Brannon, W., Virkar, Y., & Thompson, B.** (2023). Dubbing in practice: A large scale study of human localization with insights for automatic dubbing. *Transactions of the Association for Computational Linguistics*, 11, 419–435. [https://doi.org/10.1162/tacl_a_00551](https://doi.org/10.1162/tacl_a_00551)
6.  **Jia, Y., et al.** (2018). Transfer learning from speaker verification to multispeaker text-to-speech synthesis. In *Advances in Neural Information Processing Systems 31 (NeurIPS 2018)*. NeurIPS. [https://proceedings.neurips.cc/paper/2018/hash/6832a7b24bc06775d02b7406880b93fc-Abstract.html](https://proceedings.neurips.cc/paper/2018/hash/6832a7b24bc06775d02b7406880b93fc-Abstract.html)
7.  **Barakat, H., Türk, O., & Demiroglu, C.** (2024). Deep learning-based expressive speech synthesis: A systematic review of approaches, challenges, and resources. *EURASIP Journal on Audio, Speech, and Music Processing*, 2024, Article 11. SpringerOpen. [https://doi.org/10.1186/s13636-024-00329-7](https://doi.org/10.1186/s13636-024-00329-7)
8.  **Radford, A., Kim, J. W., Xu, T., Brockman, G., McLeavey, C., & Sutskever, I.** (2023). Robust speech recognition via large-scale weak supervision. In *Proceedings of the 40th International Conference on Machine Learning (ICML 2023)*. Proceedings of Machine Learning Research. [https://proceedings.mlr.press/v202/radford23a.html](https://proceedings.mlr.press/v202/radford23a.html)
9.  **OpenAI.** (2024). Voice translation into different languages using GPT-4o. *OpenAI Developers Cookbook*. [https://developers.openai.com/cookbook/examples/voice_solutions/voice_translation_into_different_languages_using_gpt-4o/](https://developers.openai.com/cookbook/examples/voice_solutions/voice_translation_into_different_languages_using_gpt-4o/)
10. **Jia, Y., Tadmor Ramanovich, M., Remez, T., & Pomerantz, R.** (2021). Translatotron 2: High-quality direct speech-to-speech translation with voice preservation. *arXiv*. [https://arxiv.org/abs/2107.08661](https://arxiv.org/abs/2107.08661)
11. **ElevenLabs.** (n.d.). Voice cloning. *ElevenLabs Documentation*. [https://elevenlabs.io/docs/eleven-creative/voices/voice-cloning](https://elevenlabs.io/docs/eleven-creative/voices/voice-cloning)
12. **ElevenLabs.** (n.d.). Edit voice settings (Update voice settings API). *ElevenLabs API Reference*. [https://elevenlabs.io/docs/api-reference/voices/settings/update](https://elevenlabs.io/docs/api-reference/voices/settings/update)
13. **FFmpeg Developers.** (n.d.). FFmpeg filters documentation. *FFmpeg Project*. [https://ffmpeg.org/ffmpeg-filters.html](https://ffmpeg.org/ffmpeg-filters.html)
14. **Livingstone, S. R., & Russo, F. A.** (2018). The Ryerson Audio-Visual Database of Emotional Speech and Song (RAVDESS): A dynamic, multimodal set of facial and vocal expressions in North American English. *PLOS ONE*, 13(5), e0196391. [https://doi.org/10.1371/journal.pone.0196391](https://doi.org/10.1371/journal.pone.0196391)
15. **Zhou, K., Sisman, B., Liu, R., & Li, H.** (2021). Emotional voice conversion: Theory, databases and ESD. *arXiv*. [https://arxiv.org/abs/2105.14762](https://arxiv.org/abs/2105.14762)
16. **Ardila, R., et al.** (2020). Common voice: A massively-multilingual speech corpus. In *Proceedings of the Twelfth Language Resources and Evaluation Conference (LREC 2020)*. European Language Resources Association. [https://aclanthology.org/2020.lrec-1.520/](https://aclanthology.org/2020.lrec-1.520/)


