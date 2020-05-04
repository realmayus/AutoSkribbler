import functools
import sys
import time
import traceback
import urllib
import urllib.request
from io import BytesIO

from PIL import Image
from PIL.ImageQt import ImageQt
from PyQt5.QtCore import Qt, QThread
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout, QSizePolicy, QGridLayout, QGroupBox, \
    QHBoxLayout, QPushButton, QCommandLinkButton, QFileDialog, QInputDialog, QMessageBox
from pynput import mouse, keyboard
from pynput.mouse import Controller, Button
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

WEBDRIVER_PATH = "/home/marius/chromedriver"



class MainWindow(QWidget):
    def __init__(self, *args, **kwargs):
        QWidget.__init__(self, None, Qt.WindowStaysOnTopHint, *args, **kwargs)

        self.ImgOriginSelector = ImgOriginSelector(self)
        self.select_coords_thread = SelectCoordsThread(self)
        self.ImageDrawingThread = ImageDrawingThread(self)

        self.layout = QGridLayout()
        self.resize(350, 440)
        self.setWindowTitle("AutoSkribbler")
        self.headline = QLabel("AutoSkribbler", self)
        self.headline.setFont(QFont("Sans Serif", 20, 600))
        self.headline.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.headline.setAlignment(Qt.AlignHCenter)
        self.layout.addWidget(self.headline, 0, 0)

        self.groupbox = QGroupBox("Coordinates")
        self.vbox = QVBoxLayout()
        self.coordCanvas = QLabel("Canvas (top left): ")
        self.coordColors = QLabel("Colors (top left): ")
        self.vbox.addWidget(self.coordCanvas)
        self.vbox.addWidget(self.coordColors)
        self.groupbox.setLayout(self.vbox)
        self.layout.addWidget(self.groupbox, 1, 0)


        self.selImgGroupbox = QGroupBox("Selected Image")
        self.vboxSelImg = QVBoxLayout()
        self.imgPreview = QLabel()
        self.imgPreview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.imgPreview.setAlignment(Qt.AlignHCenter)

        # self.imgPreviewScene = QGraphicsScene()
        # self.imgPreview = QGraphicsView(self.imgPreviewScene)
        self.vboxSelImg.addWidget(self.imgPreview)
        self.selImgGroupbox.setLayout(self.vboxSelImg)
        self.layout.addWidget(self.selImgGroupbox, 2, 0)

        self.currentActionLabel = QLabel(" ")
        self.currentActionLabel.setFont(QFont("Sans Serif", 16, 600))
        self.currentActionLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.currentActionLabel.setAlignment(Qt.AlignHCenter)
        self.layout.addWidget(self.currentActionLabel, 4, 0)

        self.currentActionSubLabel = QLabel(" ")
        self.currentActionSubLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.currentActionSubLabel.setAlignment(Qt.AlignHCenter)
        self.layout.addWidget(self.currentActionSubLabel, 5, 0)


        self.buttonbox = QHBoxLayout()
        self.btnSetCoords = QPushButton("Set Coords")
        self.btnSetCoords.clicked.connect(self.set_coords_btn_click)
        self.btnSelImg = QPushButton("Select Image")
        self.btnSelImg.clicked.connect(self.sel_img_btn_click)
        self.btnStartDraw = QPushButton("Start Drawing")
        self.btnStartDraw.clicked.connect(self.start_draw_btn_click)
        self.buttonbox.addWidget(self.btnSetCoords)
        self.buttonbox.addWidget(self.btnSelImg)
        self.buttonbox.addWidget(self.btnStartDraw)
        self.layout.addLayout(self.buttonbox, 6, 0)


        self.setLayout(self.layout)
        self.show()

        self.img_cache = []

        self.coords = {
            "canvasTopLeft": None,
            "colorsTopLeft": None,
        }

        self.actions = ["canvasTopLeft", "colorsTopLeft"]
        self.imgPath = None
        self.imgObj: Image = None
        self.preferLocalImg = True  # whether to prefer a local image over a grabbed image

    def sel_img_btn_click(self):
        self.ImgOriginSelector.show()

    def reload_img_preview(self):
        img: Image = None
        if self.imgPath and self.imgObj:
            if self.preferLocalImg:
                img: Image = Image.open(self.imgPath)
            else:
                img: Image = self.imgObj
        elif self.imgPath:
            img: Image = Image.open(self.imgPath)
        elif self.imgObj:
            img: Image = self.imgObj
        img = img.convert("RGB")
        img.thumbnail((200, 200), Image.NEAREST)
        qimg = ImageQt(img)
        pixmap = QPixmap.fromImage(qimg)
        self.imgPreview.setPixmap(pixmap)


    def set_coords_btn_click(self):
        self.select_coords_thread.finished.connect(self.set_coords_finished)
        self.select_coords_thread.start()
        self.btnSetCoords.setEnabled(False)
        self.btnSelImg.setEnabled(False)
        self.btnStartDraw.setEnabled(False)
        self.currentActionLabel.setText("Selecting Coords…")
        self.currentActionSubLabel.setText("Click at the top left of the canvas first, \nthen at the top left of the color palette.")

    def set_coords_finished(self):
        self.currentActionLabel.setText(" ")
        self.currentActionSubLabel.setText(" ")
        self.btnSetCoords.setEnabled(True)
        self.btnSelImg.setEnabled(True)
        self.btnStartDraw.setEnabled(True)

    def start_draw_btn_click(self):
        img = None
        if self.imgPath and self.imgObj:
            if self.preferLocalImg:
                img = Image.open(self.imgPath)
            else:
                img = self.imgObj
        elif self.imgPath:
            img = Image.open(self.imgPath)
        elif self.imgObj:
            img = self.imgObj

        if not self.coords['canvasTopLeft'] or not self.coords['colorsTopLeft']:
            QMessageBox.warning(self, "Error", "At least one coord is invalid.\nPlease set the coordinates first.")
            return
        if not img:
            QMessageBox.warning(self, "Error", "No image selected.\nPlease select an image first.")
            return

        self.btnStartDraw.setEnabled(False)
        self.btnSelImg.setEnabled(False)
        self.btnSetCoords.setEnabled(False)
        self.currentActionLabel.setText("Currently drawing…")
        self.currentActionSubLabel.setText("Press ESC to kill")
        self.ImageDrawingThread.set_img(img)
        self.ImageDrawingThread.finished.connect(self.img_drawing_done)
        self.ImageDrawingThread.start()

    def img_drawing_done(self):
        print("done with drawing!")
        self.btnStartDraw.setEnabled(True)
        self.btnSelImg.setEnabled(True)
        self.btnSetCoords.setEnabled(True)
        self.currentActionLabel.setText(" ")
        self.currentActionSubLabel.setText(" ")


class ImgOriginSelector(QWidget):
    def __init__(self, main_window_instance, *args, **kwargs):
        QWidget.__init__(self, None, Qt.WindowStaysOnTopHint, *args, **kwargs)
        self.main_window = main_window_instance
        self.layout = QGridLayout()
        self.resize(350, 180)
        self.setWindowTitle("Select Image Origin")

        self.headline = QLabel("From where do you want to load the image?", self)
        self.headline.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.headline.setAlignment(Qt.AlignHCenter)
        self.layout.addWidget(self.headline, 0, 0)

        self.buttonlayout = QVBoxLayout()
        local_image_button = QCommandLinkButton("Use local image")
        local_image_button.clicked.connect(self.select_local_img)
        self.buttonlayout.addWidget(local_image_button)
        grab_image_button = QCommandLinkButton("Grab image from Google Images")
        grab_image_button.clicked.connect(self.grab_img)
        self.buttonlayout.addWidget(grab_image_button)
        self.layout.addLayout(self.buttonlayout, 1, 0)
        self.setLayout(self.layout)

        self.GrabImagesThread = GrabImagesThread(self.main_window)
        self.GrabSelector = GrabSelector(self.main_window)

    def select_local_img(self):
        filediag = QFileDialog()
        filediag.setAcceptMode(QFileDialog.AcceptOpen)
        filediag.setFileMode(QFileDialog.ExistingFile)
        path = filediag.getOpenFileName(self, "Open local image", filter="Image Files (*.jpg *.jpeg *.png *.gif)")
        path = str(path[0])
        self.main_window.imgPath = path
        self.main_window.reload_img_preview()
        self.main_window.preferLocalImg = True
        print(self.main_window.imgPath)
        self.close()


    def grab_img(self):
        text, ok = QInputDialog.getText(self, 'Enter search term', 'Search term:')
        if ok:
            self.GrabImagesThread.set_query(text)
            self.GrabImagesThread.finished.connect(self.img_download_done)
            self.GrabImagesThread.start()
            self.main_window.btnSetCoords.setEnabled(False)
            self.main_window.btnSelImg.setEnabled(False)
            self.main_window.btnStartDraw.setEnabled(False)
            self.main_window.currentActionLabel.setText("Grabbing images…")
            self.close()

    def img_download_done(self):
        self.main_window.btnSetCoords.setEnabled(True)
        self.main_window.btnStartDraw.setEnabled(True)
        self.main_window.currentActionLabel.setText(" ")
        self.main_window.currentActionSubLabel.setText(" ")
        self.GrabSelector.start(self.main_window.img_cache)



class SelectCoordsThread(QThread):
    def __init__(self, main_window_instance, *args, **kwargs):
        QThread.__init__(self, *args, **kwargs)
        self.main_window_instance = main_window_instance
        self.currentPos = (0, 0)

    def run(self) -> None:
        for action in self.main_window_instance.actions:
            with mouse.Listener(
                    on_click=self.on_click) as listener:
                listener.join()
            self.main_window_instance.coords[action] = self.currentPos
            if action == 'canvasTopLeft':
                self.main_window_instance.coordCanvas.setText("Canvas (top left): " + str(self.currentPos))
            else:
                self.main_window_instance.coordColors.setText("Colors (top left): " + str(self.currentPos))


    def on_click(self, x, y, button, pressed):
        self.currentPos = (x, y)
        if not pressed:
            # Stop listener
            return False


class GrabImagesThread(QThread):
    def __init__(self, main_window_instance, *args, **kwargs):
        QThread.__init__(self, *args, **kwargs)
        self.main_window_instance = main_window_instance
        self.query = None

    def set_query(self, query):
        self.query = query

    def run(self) -> None:
        url_list = Utils.fetch_image_urls(self.main_window_instance, self.query, 9, 0.2)
        lis = []
        i = 0
        for url in url_list:
            self.main_window_instance.currentActionSubLabel.setText("Downloading " + str(i + 1) + "/9")
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            try:
                res = urllib.request.urlopen(req)
                raw_data = res.read()
                img = Image.open(BytesIO(raw_data))
                img.thumbnail((200, 200), Image.NEAREST)
                img = img.convert("RGB")
                lis.append(img)
            except Exception:
                print("error")
            i += 1
        self.main_window_instance.img_cache = lis


class GrabSelector(QWidget):
    def __init__(self, main_window_instance, *args, **kwargs):
        QWidget.__init__(self, None, Qt.WindowStaysOnTopHint, *args, **kwargs)
        self.main_window = main_window_instance
        self.layout = QGridLayout()
        self.resize(700, 500)
        self.setWindowTitle("Select image to draw")

        self.headline = QLabel("Select image to draw", self)
        self.headline.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.headline.setAlignment(Qt.AlignHCenter)
        self.layout.addWidget(self.headline, 0, 0)

        self.imggrid = QGridLayout()
        self.layout.addLayout(self.imggrid, 1, 0)

        self.cancelbtn = QPushButton("Cancel")
        self.cancelbtn.clicked.connect(self.cancel)
        self.layout.addWidget(self.cancelbtn)
        self.setLayout(self.layout)

        self.qimages = []
        self.pilimages = []

    def closeEvent(self, event) -> None:
        self.prepare_close()
        super(GrabSelector, self).closeEvent(event)

    def prepare_close(self):
        self.qimages = []
        self.pilimages = []
        self.main_window.img_cache = []
        for i in reversed(range(self.imggrid.count())):
            self.imggrid.itemAt(i).widget().setParent(None)
        self.main_window.btnSelImg.setEnabled(True)


    def cancel(self):
        self.prepare_close()
        self.close()

    def start(self, img_list):
        row = 0
        col = 0
        self.pilimages = img_list
        self.qimages = [ImageQt(im) for im in self.pilimages]  # workaround for weird image glitching bug in PyQt

        i = 0
        for qimg in self.qimages:
            label = QLabel()
            label.setPixmap(QPixmap.fromImage(qimg))
            label.mousePressEvent = functools.partial(self.on_img_select, pil_img_obj=self.pilimages[i])
            self.imggrid.addWidget(label, row, col)

            if col < 2:
                col += 1
            else:
                row += 1
                col = 0
            i += 1
        self.show()


    def on_img_select(self, event, pil_img_obj: Image):
        # print(type(pil_img_obj))
        # pil_img_obj.show()
        print("Selected image!")
        self.main_window.imgObj = pil_img_obj
        self.main_window.preferLocalImg = False
        self.main_window.reload_img_preview()
        self.close()
        # self.main_window.img_obj = event.


class ImageDrawingThread(QThread):
    def __init__(self, main_window_instance, *args, **kwargs):
        QThread.__init__(self, *args, **kwargs)
        self.main_window_instance = main_window_instance
        self.img = None
        available_colors = [255, 255, 255, 193, 193, 193, 239, 19, 11, 255, 115, 0, 255, 228, 0, 0, 204, 0, 0, 178, 255, 35, 31, 211, 163, 0, 186, 211, 124, 170, 160, 82, 45, 0, 0, 0, 76, 76, 76, 116, 11, 7, 194, 56, 0, 232, 162, 0, 0, 85, 16, 0, 86, 158, 14, 8, 101, 85, 0, 105, 167, 85, 116, 99, 48, 13]

        # adding placeholders because Pillow pallets need to have exactly 768 values
        for _t in range(768-66):
            available_colors.append(0)

        # Creating an image that we apply the skribbl.io palette to (using that later as a template)
        self.pal_image = Image.new("P", (16, 16))
        self.pal_image.putpalette(available_colors)

        self.prev_cursor = (0, 0)
        self.mouse_controller = Controller()

    def set_img(self, img_obj):
        self.img = img_obj

    def draw_pixel(self, x, y, step_size):
        # mouse_controller.position = coords["canvasTopLeft"]
        cX = self.main_window_instance.coords['canvasTopLeft'][0]
        cY = self.main_window_instance.coords['canvasTopLeft'][1]
        pX, pY = self.prev_cursor

        if pX < x and pY < y:
            self.mouse_controller.position = (cX + (x * step_size), cY + (y * step_size))
        elif pX > x and pY > y:
            self.mouse_controller.position = (cX + (x * step_size), cY + (y * step_size))
        elif pX > x and pY < y:
            self.mouse_controller.position = (cX + (x * step_size), cY + (y * step_size))
        elif pX < x and pY > y:
            self.mouse_controller.position = (cX + (x * step_size), cY + (y * step_size))
        elif pX == x and pY > y:
            self.mouse_controller.position = (cX + x, cY + (y * step_size))
        elif pX == x and pY < y:
            self.mouse_controller.position = (cX + x, cY + (y * step_size))
        elif pX > x and pY == y:
            self.mouse_controller.position = (cX + (x * step_size), cY + y)
        elif pX < x and pY == y:
            self.mouse_controller.position = (cX + (x * step_size), cY + y)

        self.prev_cursor = self.mouse_controller.position
        self.mouse_controller.click(Button.left)

    def move_one_step_to_right(self, step_size):
        self.mouse_controller.move(step_size, 0)

    def set_brush(self):
        self.mouse_controller.position = self.main_window_instance.coords['colorsTopLeft']
        print("setting brush")
        self.mouse_controller.move(492, 24)
        self.mouse_controller.press(Button.left)
        self.mouse_controller.release(Button.left)

    def set_color(self, r, g, b):
        """yes I do know that this is dirty af but who cares :p"""
        self.mouse_controller.position = self.main_window_instance.coords['colorsTopLeft']
        print("setting color to " + str(r) + ", " + str(g) + ", " + str(b))
        r = int(r)
        g = int(g)
        b = int(b)
        if r == 255 and g == 255 and b == 255:
            self.mouse_controller.move(12, 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 193 and g == 193 and b == 193:
            self.mouse_controller.move(24 + 12, 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 239 and g == 19 and b == 11:
            self.mouse_controller.move(24 * 2 + 12, 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 255 and g == 115 and b == 0:
            self.mouse_controller.move(24 * 3 + 12, 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 255 and g == 228 and b == 0:
            self.mouse_controller.move(24 * 4 + 12, 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 0 and g == 204 and b == 0:
            self.mouse_controller.move(24 * 5 + 12, 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 0 and g == 178 and b == 255:
            self.mouse_controller.move(24 * 6 + 12, 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 35 and g == 31 and b == 211:
            self.mouse_controller.move(24 * 7 + 12, 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 163 and g == 0 and b == 186:
            self.mouse_controller.move(24 * 8 + 12, 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 211 and g == 124 and b == 170:
            self.mouse_controller.move(24 * 9 + 12, 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 160 and g == 82 and b == 45:
            self.mouse_controller.move(24 * 10 + 12, 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 0 and g == 0 and b == 0:
            self.mouse_controller.move(12, 24 + 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 76 and g == 76 and b == 76:
            self.mouse_controller.move(24 * 1 + 12, 24 + 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 116 and g == 11 and b == 7:
            self.mouse_controller.move(24 * 2 + 12, 24 + 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 194 and g == 56 and b == 0:
            self.mouse_controller.move(24 * 3 + 12, 24 + 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 232 and g == 162 and b == 0:
            self.mouse_controller.move(24 * 4 + 12, 24 + 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 0 and g == 85 and b == 16:
            self.mouse_controller.move(24 * 5 + 12, 24 + 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 0 and g == 86 and b == 158:
            self.mouse_controller.move(24 * 6 + 12, 24 + 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 14 and g == 8 and b == 101:
            self.mouse_controller.move(24 * 7 + 12, 24 + 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 85 and g == 0 and b == 105:
            self.mouse_controller.move(24 * 8 + 12, 24 + 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 167 and g == 85 and b == 116:
            self.mouse_controller.move(24 * 9 + 12, 24 + 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        elif r == 99 and g == 48 and b == 13:
            self.mouse_controller.move(24 * 10 + 12, 24 + 12)
            self.mouse_controller.press(Button.left)
            self.mouse_controller.release(Button.left)
        else:
            app.warningBox("Error", "Couldn't find color R" + str(r) + " G" + str(g) + " B" + str(b))

    def run(self) -> None:
        pixel_colors = {}

        def has_neighbor(pixel1, pixel_map) -> bool:
            # print(1)
            # if pixel1 in pixel_map:
            #     index_in_pixel_map = pixel_map.index(pixel1)
            #     print(2)
            #     pixelX, pixelY = pixel1
            #     if len(pixel_map) - 1 == index_in_pixel_map:  # check if there even is a next pixel
            #         print(3)
            #         nextPixelX, nextPixelY = pixel_map[index_in_pixel_map + 1]  # nextPixel refers to the next pixel in the pixel map, not next to it in the pixel *grid*
            #         if pixelY == nextPixelY and pixelX + 1 == nextPixelX:  # check if the current pixel and the next pixel are in the same line and if the current pixel plus one is the next pixel, i.e. it the next pixel is directly next to the current pixel
            #             return True
            #         else:
            #             return False
            #     else:
            #         return False
            # else:
            #     return False
            pixelX, pixelY = pixel1
            pixelNext = (pixelX + 1, pixelY)
            if pixelNext in pixel_map:
                return True
            else:
                return False

        try:
            self.img.thumbnail((133, 100), Image.NEAREST)
            self.img = self.img.convert("RGB").quantize(palette=self.pal_image)
            width, height = self.img.size
            self.img = self.img.convert("RGB")
            for y in range(height):
                for x in range(width):
                    r, g, b = self.img.getpixel((x, y))

                    if r == 255 and g == 255 and b == 255:
                        continue  # skip white because canvas is… white

                    key = ' '.join([str(r), str(g), str(b)])
                    if key not in pixel_colors:
                        pixel_colors[key] = []
                    pixel_colors[key].append((x, y))

            print(pixel_colors)
            self.set_brush()
            for kay in pixel_colors:
                print(kay)

                r, g, b = kay.split(' ')
                print(r, g, b)
                self.set_color(r, g, b)
                time.sleep(1)
                i = 0
                skip_amount = 0
                for pixel in pixel_colors[kay]:
                    if skip_amount > 0:
                        skip_amount -= 1
                        continue
                    x, y = pixel
                    if has_neighbor(pixel, pixel_colors[kay]):
                        print("pixel ", x, y, " has a neighbor")
                        canvasTopX, canvasTopY = self.main_window_instance.coords['canvasTopLeft']
                        self.mouse_controller.position = (canvasTopX + (x * 6), canvasTopY + (y * 6))
                        self.mouse_controller.press(Button.left)  # press the mouse button
                        virtual_pixel = pixel  # the virtual_pixel is the pixel that will iterate through the current line
                        currently_skipped = 0
                        while has_neighbor(virtual_pixel, pixel_colors[kay]):
                            print("iterating through the pixel", virtual_pixel[0], y, "'s neigbors…")
                            self.move_one_step_to_right(6)  # move mouse six pixels to the right
                            virtual_pixel = (virtual_pixel[0] + 1, y)  # move "virtual pixel" one to the right
                            currently_skipped += 1
                        self.mouse_controller.release(Button.left)  # release the mouse button
                        skip_amount = currently_skipped
                    else:
                        print("pixel ", x, y, " has no neighbor")
                        self.draw_pixel(x, y, 6)
                    time.sleep(0.0005)
                    i += 1


        except Exception as e:
            print(traceback.format_exc())
            # app.warningBox("An error occurred", "An error occurred:\n" + str(e))


class Utils:
    @staticmethod
    def fetch_image_urls(main_window_instance, query: str, max_links_to_fetch: int, sleep_between_interactions = 1):
        def scroll_to_end(wd):
            wd.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(sleep_between_interactions)

            # build the google query

        search_url = "https://www.google.com/search?safe=off&site=&tbm=isch&source=hp&q={q}&oq={q}&gs_l=img"

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920x1080")
        wd = webdriver.Chrome(executable_path=WEBDRIVER_PATH, options=chrome_options)
        wd.get(search_url.format(q=query))

        image_urls = set()
        image_count = 0
        results_start = 0
        while image_count < max_links_to_fetch:
            scroll_to_end(wd)
            # get all image thumbnail results
            thumbnail_results = wd.find_elements_by_css_selector("img.Q4LuWd")
            number_results = len(thumbnail_results)
            print(f"Found: {number_results} search results. Extracting links from {results_start}:{number_results}")
            for img in thumbnail_results[results_start:number_results]:
                main_window_instance.currentActionSubLabel.setText("Grabbing " + str(image_count + 1) + "/9")
                # try to click every thumbnail such that we can get the real image behind it
                try:
                    img.click()
                    time.sleep(sleep_between_interactions)
                except Exception:
                    continue

                # extract image urls
                actual_images = wd.find_elements_by_css_selector('img.n3VNCb')
                for actual_image in actual_images:
                    if actual_image.get_attribute('src') and 'http' in actual_image.get_attribute('src'):
                        image_urls.add(actual_image.get_attribute('src'))

                image_count = len(image_urls)

                if len(image_urls) >= max_links_to_fetch:
                    print(f"Found: {len(image_urls)} image links, done!")
                    return image_urls

            # move the result startpoint further down
            results_start = len(thumbnail_results)
        return None


def handle_esc(key):
    if key == keyboard.Key.esc:
        print("stopped through ESC")
        app.quit()
        sys.exit(1)


key_listener = keyboard.Listener(
    on_release=handle_esc)
key_listener.start()


app = QApplication(sys.argv)
win = MainWindow()
sys.exit(app.exec_())

