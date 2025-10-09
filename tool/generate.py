import csv

import cv2
import numpy as np

'''
传入一个列表最多可以有4个参数
'''
def generate_fgimage(target, embeddings_layers):
    assert target in ["ムラサメa", "ムラサメb"]
    with open(f"./fgimages/{target}.txt", encoding='utf-16 le') as cf:
        infos = list(csv.reader(cf, delimiter='\t'))

    if target == "ムラサメa":
        all_base = infos[57:65]
    else:
        all_base = infos[47:51]

    all_positions = [(int(x[2]), int(x[3]), int(x[4]), int(x[5]))
                     for name in embeddings_layers for x in infos if x[9] == str(name)]
    all_base = [(int(x[2]), int(x[3]), int(x[4]), int(x[5]))
                for x in all_base]

    all_positions = [(pos[0] - min(pos[0] for pos in all_base), pos[1] - min(pos[1] for pos in all_base), pos[2], pos[3])
                     for pos in all_positions]

    canvas_scale = (max([(x[0] + x[2]) for x in all_positions]),
                    max([(x[1] + x[3]) for x in all_positions]))

    canvas = np.zeros((canvas_scale[1], canvas_scale[0], 4), dtype=np.uint8)

    for idx, pos in enumerate(all_positions):
        path = f"./fgimages/{target}_{embeddings_layers[idx]}.png"
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), -1)
        if image is not None:
            x_offset = pos[0]
            y_offset = pos[1]
            h, w = image.shape[:2]
            alpha_img = image[..., 3:] / 255.0
            alpha_canvas = 1.0 - alpha_img
            for c in range(3):
                canvas[y_offset:y_offset + h, x_offset:x_offset + w, c] = (
                    alpha_img[..., 0] * image[..., c] +
                    alpha_canvas[..., 0] * canvas[y_offset:y_offset +
                                                  h, x_offset:x_offset + w, c]
                )
            canvas[y_offset:y_offset + h, x_offset:x_offset + w, 3] = (
                np.maximum(
                    image[..., 3], canvas[y_offset:y_offset + h, x_offset:x_offset + w, 3])
            )

    return canvas
