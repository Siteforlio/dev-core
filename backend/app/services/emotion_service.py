import base64
import asyncio

# Heavy imports deferred to _ensure_loaded() — called on first use
_mp = None
_cv2 = None
_np = None
_mp_face_mesh = None


def _ensure_loaded():
    global _mp, _cv2, _np, _mp_face_mesh
    if _mp is not None:
        return
    import mediapipe as mp
    import cv2
    import numpy as np
    _mp = mp
    _cv2 = cv2
    _np = np
    _mp_face_mesh = mp.solutions.face_mesh

# Landmark indices
LEFT_EYE = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
RIGHT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
MOUTH_TOP = 13
MOUTH_BOTTOM = 14
LEFT_BROW = [70, 63, 105, 66, 107]
RIGHT_BROW = [300, 293, 334, 296, 336]

# Iris centre landmarks (refined landmarks required)
LEFT_IRIS_CENTER = 473
RIGHT_IRIS_CENTER = 468
# Outer eye corners
LEFT_EYE_INNER = 362
LEFT_EYE_OUTER = 263
RIGHT_EYE_INNER = 133
RIGHT_EYE_OUTER = 33


def _eye_aspect_ratio(landmarks, indices: list[int]) -> float:
    pts = [(landmarks[i].x, landmarks[i].y) for i in indices]
    top = pts[1:7]
    bot = pts[9:15]
    vert = sum(abs(t[1] - b[1]) for t, b in zip(top, bot)) / 6
    horiz = abs(pts[0][0] - pts[8][0]) + 1e-6
    return vert / horiz


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class EmotionService:
    def _run_facemesh(self, image):
        _ensure_loaded()
        with _mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
        ) as fm:
            return fm.process(_cv2.cvtColor(image, _cv2.COLOR_BGR2RGB))

    def _landmarks_to_emotion(self, landmarks) -> str:
        _ensure_loaded()
        left_ear = _eye_aspect_ratio(landmarks, LEFT_EYE)
        right_ear = _eye_aspect_ratio(landmarks, RIGHT_EYE)
        avg_ear = (left_ear + right_ear) / 2

        mouth_gap = abs(landmarks[MOUTH_TOP].y - landmarks[MOUTH_BOTTOM].y)

        brow_y = _np.mean([landmarks[i].y for i in LEFT_BROW + RIGHT_BROW])
        eye_y = _np.mean([landmarks[i].y for i in LEFT_EYE[:4] + RIGHT_EYE[:4]])
        brow_raise = eye_y - brow_y

        if avg_ear < 0.15:
            return "nervous"
        if brow_raise > 0.04 and mouth_gap > 0.03:
            return "engaged"
        if brow_raise > 0.03:
            return "uncertain"
        if avg_ear > 0.25 and mouth_gap < 0.02:
            return "confident"
        return "neutral"

    def _landmarks_to_scores(self, landmarks) -> tuple[float, float]:
        """Return (nervousness_score, confidence_score) both in [0, 1]."""
        _ensure_loaded()
        left_ear = _eye_aspect_ratio(landmarks, LEFT_EYE)
        right_ear = _eye_aspect_ratio(landmarks, RIGHT_EYE)
        avg_ear = (left_ear + right_ear) / 2

        mouth_gap = abs(landmarks[MOUTH_TOP].y - landmarks[MOUTH_BOTTOM].y)

        brow_y = _np.mean([landmarks[i].y for i in LEFT_BROW + RIGHT_BROW])
        eye_y = _np.mean([landmarks[i].y for i in LEFT_EYE[:4] + RIGHT_EYE[:4]])
        brow_raise = eye_y - brow_y

        # Nervousness: high when EAR is low (squinting) + brows tense
        nervousness = _clamp(1.0 - (avg_ear - 0.10) / 0.20)

        # Confidence: high when EAR open + brows relaxed + mouth slightly open
        confidence = _clamp(
            0.4 * ((avg_ear - 0.15) / 0.15)
            + 0.4 * (1.0 - max(brow_raise, 0) / 0.05)
            + 0.2 * _clamp(mouth_gap / 0.04)
        )

        return round(nervousness, 3), round(confidence, 3)

    def _landmarks_to_gaze(self, landmarks) -> str:
        """Estimate gaze direction from iris position relative to eye corners."""
        _ensure_loaded()
        try:
            # Left iris
            l_iris_x = landmarks[LEFT_IRIS_CENTER].x
            l_inner_x = landmarks[LEFT_EYE_INNER].x
            l_outer_x = landmarks[LEFT_EYE_OUTER].x
            l_ratio = (l_iris_x - l_inner_x) / (l_outer_x - l_inner_x + 1e-6)

            # Right iris
            r_iris_x = landmarks[RIGHT_IRIS_CENTER].x
            r_inner_x = landmarks[RIGHT_EYE_INNER].x
            r_outer_x = landmarks[RIGHT_EYE_OUTER].x
            r_ratio = (r_iris_x - r_inner_x) / (r_outer_x - r_inner_x + 1e-6)

            avg_ratio = (l_ratio + r_ratio) / 2

            if avg_ratio < 0.35:
                return "left"
            if avg_ratio > 0.65:
                return "right"

            # Vertical: iris y vs eye centre y
            iris_y = (landmarks[LEFT_IRIS_CENTER].y + landmarks[RIGHT_IRIS_CENTER].y) / 2
            eye_centre_y = _np.mean([landmarks[i].y for i in LEFT_EYE[:4] + RIGHT_EYE[:4]])
            if iris_y < eye_centre_y - 0.01:
                return "up"
            if iris_y > eye_centre_y + 0.01:
                return "down"
            return "center"
        except (IndexError, AttributeError):
            return "center"

    def _decode_frame(self, frame_b64: str):
        """Decode a base64 JPEG/PNG to a BGR numpy array. Returns None on failure."""
        _ensure_loaded()
        try:
            img_bytes = base64.b64decode(frame_b64)
            arr = _np.frombuffer(img_bytes, dtype=_np.uint8)
            return _cv2.imdecode(arr, _cv2.IMREAD_COLOR)
        except Exception:
            return None

    async def analyze_frame(self, frame_b64: str) -> dict:
        loop = asyncio.get_event_loop()

        def _process():
            image = self._decode_frame(frame_b64)
            if image is None:
                return None
            try:
                return self._run_facemesh(image)
            except Exception:
                return None

        result = await loop.run_in_executor(None, _process)

        if result is None or not result.multi_face_landmarks:
            return {
                "emotion": "neutral",
                "eye_contact": False,
                "confidence": 0.5,
                "nervousness_score": 0.5,
                "confidence_score": 0.5,
                "gaze_direction": "center",
            }

        landmarks = result.multi_face_landmarks[0].landmark
        emotion = self._landmarks_to_emotion(landmarks)
        nervousness_score, confidence_score = self._landmarks_to_scores(landmarks)
        gaze_direction = self._landmarks_to_gaze(landmarks)

        try:
            left_ear = _eye_aspect_ratio(landmarks, LEFT_EYE)
            right_ear = _eye_aspect_ratio(landmarks, RIGHT_EYE)
            eye_contact = (left_ear + right_ear) / 2 > 0.18
        except (IndexError, TypeError):
            eye_contact = False

        return {
            "emotion": emotion,
            "eye_contact": eye_contact,
            "confidence": confidence_score,          # backward-compat alias
            "nervousness_score": nervousness_score,
            "confidence_score": confidence_score,
            "gaze_direction": gaze_direction,
        }
