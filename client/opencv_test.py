import cv2

frame_count = 0
ip_cam_url = "rtsp://gsdemo.viasat.io:1935/live/camera1.sdp"
cap = cv2.VideoCapture(str(ip_cam_url), cv2.CAP_FFMPEG)

while True:
    ret, frame = cap.read()
    print("Debug: OpenCV 'Read' return value: {}".format(ret))

    if ret is False:
        break

    retval, buff = cv2.imencode(".jpg", frame)
    img_bytes = bytearray(buff)
    target = open("img_{}.jpg".format(frame_count), 'wb')
    target.write(img_bytes)
    target.close()
    frame_count += 1

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()