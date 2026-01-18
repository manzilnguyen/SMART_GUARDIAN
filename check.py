from ultralytics import YOLO

yolo = YOLO("weapon.pt")

print("Classes:", yolo.names)
print("Số class:", len(yolo.names))
print(yolo.model)        # DetectionModel
print(yolo.model.names) # class names
print(yolo.model.nc)    # số class
