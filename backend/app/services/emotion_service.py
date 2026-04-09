import base64
import asyncio
import numpy as np
import mediapipe as mp
import cv2

mp_face_mesh = mp.solutions.face_mesh

# Landmark indices
LEFT_EYE = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
RIGHT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
MOUTH_TOP = 13
MOUTH_BOTTOM = 14
LEFT_BROW = [70, 63, 105, 66, 107]
RIGHT_BROW = [300, 293, 334, 296, 336]


def _eye_aspect_ratio(landmarks, indices: list[int]) -> float:
    pts = [(landmarks[i].x, landmarks[i].y) for i in indices]
    # Simplified EAR: vertical distance / horizontal distance
    top = pts[1:7]
    bot = pts[9:15]
    vert = sum(abs(t[1] - b[1]) for t, b in zip(top, bot)) / 6
    horiz = abs(pts[0][0] - pts[8][0]) + 1e-6
    return vert / horiz


class EmotionService:
    def _run_facemesh(self, image: np.ndarray):
        with mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
        ) as fm:
            return fm.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    def _landmarks_to_emotion(self, landmarks) -> str:
        left_ear = _eye_aspect_ratio(landmarks, LEFT_EYE[:8])
        right_ear = _eye_aspect_ratio(landmarks, RIGHT_EYE[:8])
        avg_ear = (left_ear + right_ear) / 2

        mouth_gap = abs(landmarks[MOUTH_TOP].y - landmarks[MOUTH_BOTTOM].y)

        # Brow raise — higher y means lower on screen (inverted)
        brow_y = np.mean([landmarks[i].y for i in LEFT_BROW + RIGHT_BROW])
        eye_y = np.mean([landmarks[i].y for i in LEFT_EYE[:4] + RIGHT_EYE[:4]])
        brow_raise = eye_y - brow_y  # positive → brows raised

        if avg_ear < 0.15:
            return "nervous"
        if brow_raise > 0.04 and mouth_gap > 0.03:
            return "engaged"
        if brow_raise > 0.03:
            return "uncertain"
        if avg_ear > 0.25 and mouth_gap < 0.02:
            return "confident"
        return "neutral"

    async def analyze_frame(self, frame_b64: str) -> dict:
        loop = asyncio.get_event_loop()

        def _process():
            try:
                img_bytes = base64.b64decode(frame_b64)
                arr = np.frombuffer(img_bytes, dtype=np.uint8)
                image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if image is None:
                    return None
                return self._run_facemesh(image)
            except Exception:
                return None

        result = await loop.run_in_executor(None, _process)

        if result is None or not result.multi_face_landmarks:
            return {"emotion": "neutral", "eye_contact": False, "confidence": 0.5}

        landmarks = result.multi_face_landmarks[0].landmark
        emotion = self._landmarks_to_emotion(landmarks)

        left_ear = _eye_aspect_ratio(landmarks, LEFT_EYE[:8])
        right_ear = _eye_aspect_ratio(landmarks, RIGHT_EYE[:8])
        eye_contact = (left_ear + right_ear) / 2 > 0.18

        confidence_map = {
            "confident": 0.85,
            "engaged": 0.75,
            "neutral": 0.60,
            "uncertain": 0.45,
            "nervous": 0.30,
        }
        return {
            "emotion": emotion,
            "eye_contact": eye_contact,
            "confidence": confidence_map.get(emotion, 0.60),
        }
