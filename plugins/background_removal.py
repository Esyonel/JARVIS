PLUGIN = {
    "name": "background_removal",
    "description": "Canlı kamera görüntüsünün arka planını siler ve sonucu bir pencerede gösterir.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Remove background from live camera feed using OpenCV.

    This plugin opens the default camera (index 0), applies a simple background
    subtraction algorithm, and displays the processed video in a window titled
    'Arka Plan Silindi'. Press the 'q' key to stop the video feed.
    Returns a short spoken message indicating success or any encountered error.
    """
    try:
        import cv2
    except ImportError:
        return "OpenCV yüklü değil, lütfen 'pip install opencv-python' komutunu çalıştırın."

    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "Kamera açılamadı, lütfen kamera bağlantısını kontrol edin."

        # Simple background subtractor
        fgbg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=False)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Apply background subtraction mask
            fgmask = fgbg.apply(frame)
            # Clean up mask (optional)
            _, fgmask = cv2.threshold(fgmask, 250, 255, cv2.THRESH_BINARY)
            # Combine original frame with mask to isolate foreground
            result = cv2.bitwise_and(frame, frame, mask=fgmask)

            cv2.imshow('Arka Plan Silindi', result)
            # Exit when user presses 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
        return "Canlı kamera arka planı silme işlemi tamamlandı."
    except Exception as e:
        # Ensure resources are released on error
        try:
            cap.release()
            cv2.destroyAllWindows()
        except Exception:
            pass
        return f"Arka plan silme sırasında bir hata oluştu: {e}"