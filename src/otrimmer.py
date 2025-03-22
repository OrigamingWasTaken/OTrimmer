#!/usr/bin/env python3

import sys
import os
import subprocess
import tempfile
import shutil
import argparse
import glob
from datetime import datetime
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, pyqtProperty, QUrl, QTimer, QVariant, QSortFilterProxyModel, QAbstractListModel, Qt, QModelIndex, QDateTime
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtQml import QQmlApplicationEngine, qmlRegisterType, QQmlEngine, QQmlContext
from PyQt5.QtQuick import QQuickView
import PyQt5

class VideoInfo(QObject):
    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self._filepath = filepath
        self._filename = os.path.basename(filepath)
        self._filesize = os.path.getsize(filepath)
        self._last_modified = QDateTime.fromSecsSinceEpoch(int(os.path.getmtime(filepath)))
        self._thumbnail_path = self._generate_thumbnail()
        
    @pyqtProperty(str)
    def filepath(self):
        return self._filepath
        
    @pyqtProperty(str)
    def filename(self):
        return self._filename
        
    @pyqtProperty(int)
    def filesize(self):
        return self._filesize
        
    @pyqtProperty(QDateTime)
    def lastModified(self):
        return self._last_modified
        
    @pyqtProperty(str)
    def thumbnailPath(self):
        return self._thumbnail_path
        
    @pyqtProperty(str)
    def fileSizeFormatted(self):
        """Return human-readable file size"""
        size = self._filesize
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
        
    def _generate_thumbnail(self):
        """Generate a thumbnail for the video"""
        try:
            # Create a unique filename for the thumbnail
            thumbnail_dir = os.path.join(tempfile.gettempdir(), "otrimmer_thumbnails")
            os.makedirs(thumbnail_dir, exist_ok=True)
            
            # Use hash of filepath to create a unique thumbnail name
            import hashlib
            hash_object = hashlib.md5(self._filepath.encode())
            hash_name = hash_object.hexdigest()
            thumbnail_path = os.path.join(thumbnail_dir, f"{hash_name}.jpg")
            
            # Check if thumbnail already exists
            if os.path.exists(thumbnail_path):
                return QUrl.fromLocalFile(thumbnail_path).toString()
                
            # Use ffmpeg to extract a thumbnail
            if shutil.which("ffmpeg"):
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', self._filepath,
                    '-ss', '00:00:01',  # Take frame from 1 second in
                    '-vframes', '1',
                    '-vf', 'scale=320:-1',  # Scale to width of 320px
                    thumbnail_path
                ]
                
                try:
                    result = subprocess.run(cmd, capture_output=True, timeout=10)
                    if os.path.exists(thumbnail_path):
                        return QUrl.fromLocalFile(thumbnail_path).toString()
                    else:
                        print(f"Thumbnail generation failed: {result.stderr}")
                except Exception as e:
                    print(f"Error generating thumbnail: {e}")
                    # Fall back to placeholder if thumbnail generation fails
            
            # Return a fallback icon path (system icon)
            standard_icon_paths = [
                "/usr/share/icons/breeze/mimetypes/64/video-x-generic.svg",
                "/usr/share/icons/hicolor/64x64/mimetypes/video-x-generic.png",
                "/usr/share/icons/hicolor/scalable/mimetypes/video-x-generic.svg",
                "/usr/share/icons/Adwaita/64x64/mimetypes/video-x-generic.png"
            ]
            
            for icon_path in standard_icon_paths:
                if os.path.exists(icon_path):
                    return QUrl.fromLocalFile(icon_path).toString()
            
            # Fallback to empty string if no icon found
            return ""
            
        except Exception as e:
            print(f"Thumbnail error: {e}")
            # Return an empty string on any error
            return ""

class VideoGalleryModel(QAbstractListModel):
    FilepathRole = Qt.UserRole + 1
    FilenameRole = Qt.UserRole + 2
    FilesizeRole = Qt.UserRole + 3
    LastModifiedRole = Qt.UserRole + 4
    FilesizeFormattedRole = Qt.UserRole + 5
    ThumbnailPathRole = Qt.UserRole + 6
    
    # Signal when data changes
    dataChanged = pyqtSignal(QModelIndex, QModelIndex, list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._videos = []
        
    def rowCount(self, parent=QModelIndex()):
        return len(self._videos)
        
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._videos):
            return QVariant()
            
        video = self._videos[index.row()]
        
        if role == self.FilepathRole:
            return video.filepath
        elif role == self.FilenameRole:
            return video.filename
        elif role == self.FilesizeRole:
            return video.filesize
        elif role == self.LastModifiedRole:
            return video.lastModified
        elif role == self.FilesizeFormattedRole:
            return video.fileSizeFormatted
        elif role == self.ThumbnailPathRole:
            return video.thumbnailPath
            
        return QVariant()
        
    def roleNames(self):
        return {
            self.FilepathRole: b'filepath',
            self.FilenameRole: b'filename',
            self.FilesizeRole: b'filesize',
            self.LastModifiedRole: b'lastModified',
            self.FilesizeFormattedRole: b'fileSizeFormatted',
            self.ThumbnailPathRole: b'thumbnailPath'
        }
        
    @pyqtSlot(str, result=bool)
    def loadVideosFromDirectory(self, directory=None):
        """Load all video files from the specified directory"""
        if directory is None:
            directory = os.getcwd()
            
        # Common video file extensions
        video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.mpg', '.mpeg']
        
        self.beginResetModel()
        self._videos = []
        
        for ext in video_extensions:
            pattern = os.path.join(directory, f"*{ext}")
            for filepath in glob.glob(pattern):
                self._videos.append(VideoInfo(filepath))
                
        self.endResetModel()
        return len(self._videos) > 0

class VideoGallery(QObject):
    videoSelected = pyqtSignal(str)
    modelChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = VideoGalleryModel()
        self._proxy_model = QSortFilterProxyModel()
        self._proxy_model.setSourceModel(self._model)
        self._script_path = os.path.abspath(sys.argv[0])
        
    @pyqtProperty(QObject, notify=modelChanged)
    def model(self):
        return self._proxy_model
        
    @pyqtProperty(str, constant=True)
    def scriptPath(self):
        return self._script_path
        
    @pyqtSlot(str)
    def openVideoInTrimmer(self, filepath):
        """Launch the video in the trimmer using subprocess"""
        try:
            print(f"Opening video in trimmer: {filepath}")
            
            # Get the Python executable and script path
            python_exe = sys.executable
            script_path = self._script_path
            
            # Use subprocess to properly launch with arguments
            import subprocess
            
            # Launch in a new process and detach
            if sys.platform == 'win32':
                # Windows uses different creation flags
                subprocess.Popen([python_exe, script_path, filepath], 
                                 creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                # Linux/macOS
                subprocess.Popen([python_exe, script_path, filepath], 
                                 start_new_session=True)
                
            # Signal the application to close
            QTimer.singleShot(500, lambda: QGuiApplication.instance().quit())
        except Exception as e:
            print(f"Error launching trimmer: {e}")
        
    @pyqtSlot(str, result=bool)
    def loadFromDirectory(self, directory=None):
        result = self._model.loadVideosFromDirectory(directory)
        self.modelChanged.emit()
        return result
        
    @pyqtSlot(str)
    def selectVideo(self, filepath):
        self.videoSelected.emit(filepath)
        
    @pyqtSlot(int)
    def sortBy(self, role):
        """Sort the model by the specified role"""
        self._proxy_model.setSortRole(role)
        self._proxy_model.sort(0, Qt.AscendingOrder)
        self.modelChanged.emit()
        
    @pyqtSlot(int)
    def sortByDescending(self, role):
        """Sort the model by the specified role in descending order"""
        self._proxy_model.setSortRole(role)
        self._proxy_model.sort(0, Qt.DescendingOrder)
        self.modelChanged.emit()
    
    @pyqtProperty(int, constant=True)
    def filepathRole(self):
        return VideoGalleryModel.FilepathRole
        
    @pyqtProperty(int, constant=True)
    def filenameRole(self):
        return VideoGalleryModel.FilenameRole
        
    @pyqtProperty(int, constant=True)
    def filesizeRole(self):
        return VideoGalleryModel.FilesizeRole
        
    @pyqtProperty(int, constant=True)
    def lastModifiedRole(self):
        return VideoGalleryModel.LastModifiedRole

class VideoTrimmer(QObject):
    startTimeChanged = pyqtSignal()
    endTimeChanged = pyqtSignal()
    durationChanged = pyqtSignal()
    trimCompleteChanged = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)
    compressionProgressChanged = pyqtSignal(int)  # For progress updates
    compressionStarted = pyqtSignal()
    compressionFinished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_time = 0
        self._end_time = 0
        self._duration = 0
        self._video_path = ""
        self._trim_completed = False
        self._temp_output = None
        self._compressed_output = None
        self._max_size_mb = 50  # Maximum size for compressed videos in MB

    @pyqtProperty(int, notify=startTimeChanged)
    def startTime(self):
        return self._start_time

    @startTime.setter
    def startTime(self, value):
        if self._start_time != value:
            self._start_time = value
            self._trim_completed = False
            self.startTimeChanged.emit()

    @pyqtProperty(int, notify=endTimeChanged)
    def endTime(self):
        return self._end_time

    @endTime.setter
    def endTime(self, value):
        if self._end_time != value:
            self._end_time = value
            self._trim_completed = False
            self.endTimeChanged.emit()

    @pyqtProperty(int, notify=durationChanged)
    def duration(self):
        return self._duration

    @pyqtSlot(str)
    def setVideoFile(self, file_path):
        """Set the video file and get its duration"""
        # Handle both URL and string path
        if file_path.startswith('file://'):
            self._video_path = file_path.replace('file://', '')
        else:
            self._video_path = file_path
            
        # Convert to absolute path if not already
        if not os.path.isabs(self._video_path):
            self._video_path = os.path.abspath(self._video_path)
            
        print(f"Setting video file: {self._video_path}")
        
        try:
            # Check if file exists
            if not os.path.exists(self._video_path):
                self.errorOccurred.emit(f"File not found: {self._video_path}")
                return
                
            # Get video duration using ffprobe
            cmd = [
                'ffprobe', 
                '-v', 'error', 
                '-show_entries', 'format=duration', 
                '-of', 'default=noprint_wrappers=1:nokey=1', 
                self._video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self._duration = int(float(result.stdout.strip()) * 1000)  # Convert to milliseconds
                self._end_time = self._duration
                self.durationChanged.emit()
            else:
                self.errorOccurred.emit(f"Error getting video duration: {result.stderr}")
        except Exception as e:
            self.errorOccurred.emit(f"Error processing video: {str(e)}")

    @pyqtSlot(result=bool)
    def createTrim(self):
        """Create a trimmed version in memory without saving yet"""
        if not self._video_path:
            self.errorOccurred.emit("No video loaded")
            return False
            
        try:
            # Get temp directory for storing the trimmed video temporarily
            self._temp_output = os.path.join(tempfile.gettempdir(), f"trimmed_video_{os.getpid()}.mp4")
            
            # Convert milliseconds to seconds for ffmpeg
            start_seconds = self._start_time / 1000
            duration_seconds = (self._end_time - self._start_time) / 1000
            
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file if it exists
                '-i', self._video_path,
                '-ss', str(start_seconds),
                '-t', str(duration_seconds),
                '-c', 'copy',  # Use stream copy for fast trimming without re-encoding
                self._temp_output
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self._trim_completed = True
                # Generate compressed version if needed
                QTimer.singleShot(100, self._check_and_compress)
                self.trimCompleteChanged.emit("Trim created and ready to save or copy")
                return True
            else:
                self.errorOccurred.emit(f"Error trimming video: {result.stderr}")
                return False
                
        except Exception as e:
            self.errorOccurred.emit(f"Error during trimming: {str(e)}")
            return False
            
    def _check_and_compress(self):
        """Check if the trimmed video needs compression and compress it if necessary"""
        try:
            if not os.path.exists(self._temp_output):
                return
                
            # Check file size
            file_size_bytes = os.path.getsize(self._temp_output)
            file_size_mb = file_size_bytes / (1024 * 1024)
            
            if file_size_mb <= self._max_size_mb:
                # File is already small enough
                self._compressed_output = self._temp_output
                self.trimCompleteChanged.emit(f"Trim ready (Size: {file_size_mb:.1f}MB)")
                return
                
            # Need to compress
            self.trimCompleteChanged.emit(f"Compressing video ({file_size_mb:.1f}MB → {self._max_size_mb}MB max)...")
            self._compressed_output = os.path.join(tempfile.gettempdir(), f"compressed_video_{os.getpid()}.mp4")
            
            # Calculate target bitrate to achieve desired file size
            # Formula: bitrate = target_size_bytes * 8 / duration_seconds
            video_info = self._get_video_info(self._temp_output)
            duration_seconds = float(video_info.get('duration', 0))
            if duration_seconds <= 0:
                self.errorOccurred.emit("Could not determine video duration for compression")
                return
                
            target_size_bytes = self._max_size_mb * 1024 * 1024 * 0.95  # 5% buffer
            target_bitrate = int((target_size_bytes * 8) / duration_seconds)
            
            # Compress video
            cmd = [
                'ffmpeg',
                '-y',
                '-i', self._temp_output,
                '-c:v', 'libx264',
                '-b:v', f"{target_bitrate}",
                '-preset', 'medium',  # Balance between speed and compression
                '-c:a', 'aac',
                '-b:a', '128k',
                self._compressed_output
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                compressed_size_mb = os.path.getsize(self._compressed_output) / (1024 * 1024)
                self.trimCompleteChanged.emit(f"Compressed video ({file_size_mb:.1f}MB → {compressed_size_mb:.1f}MB)")
            else:
                self.errorOccurred.emit(f"Error compressing video: {result.stderr}")
                self._compressed_output = self._temp_output  # Fallback to uncompressed
        except Exception as e:
            self.errorOccurred.emit(f"Error during compression: {str(e)}")
            self._compressed_output = self._temp_output  # Fallback to uncompressed
            
    def _get_video_info(self, video_path):
        """Get video information using ffprobe"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'format=duration',
                '-of', 'json',
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                return {
                    'duration': data.get('format', {}).get('duration', 0)
                }
            return {}
        except Exception:
            return {}
    
    @pyqtSlot(int, result=bool)
    def compressToSize(self, size_mb):
        """Compress the trimmed video to a specific size in MB"""
        if not self._trim_completed:
            self.errorOccurred.emit("No trimmed video available")
            return False
        
        try:
            # Use the output of the trimming operation as the input for compression
            input_file = self._temp_output
            
            if not os.path.exists(input_file):
                self.errorOccurred.emit("Trimmed video file not found")
                return False
                
            # Create a new output file for the compressed version
            self._compressed_output = os.path.join(tempfile.gettempdir(), f"compressed_video_{os.getpid()}.mp4")
            
            # Check file size
            file_size_bytes = os.path.getsize(input_file)
            file_size_mb = file_size_bytes / (1024 * 1024)
            
            if file_size_mb <= size_mb:
                # File is already small enough
                self._compressed_output = input_file
                self.trimCompleteChanged.emit(f"Video already fits size requirement ({file_size_mb:.1f}MB)")
                return True
                
            # Notify compression started
            self.compressionStarted.emit()
            self.trimCompleteChanged.emit(f"Compressing video ({file_size_mb:.1f}MB → {size_mb}MB)...")
            
            # Calculate target bitrate to achieve desired file size
            # Formula: bitrate = target_size_bytes * 8 / duration_seconds
            video_info = self._get_video_info(input_file)
            duration_seconds = float(video_info.get('duration', 0))
            if duration_seconds <= 0:
                self.errorOccurred.emit("Could not determine video duration for compression")
                return False
                
            target_size_bytes = size_mb * 1024 * 1024 * 0.95  # 5% buffer
            target_bitrate = int((target_size_bytes * 8) / duration_seconds)
            
            # Compress video
            cmd = [
                'ffmpeg',
                '-y',
                '-i', input_file,
                '-c:v', 'libx264',
                '-b:v', f"{target_bitrate}",
                '-preset', 'medium',  # Balance between speed and compression
                '-c:a', 'aac',
                '-b:a', '128k',
                self._compressed_output
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                compressed_size_mb = os.path.getsize(self._compressed_output) / (1024 * 1024)
                self.trimCompleteChanged.emit(f"Compressed video ({file_size_mb:.1f}MB → {compressed_size_mb:.1f}MB)")
                self.compressionFinished.emit()
                return True
            else:
                self.errorOccurred.emit(f"Error compressing video: {result.stderr}")
                self._compressed_output = input_file  # Fallback to uncompressed
                self.compressionFinished.emit()
                return False
        
        except Exception as e:
            self.errorOccurred.emit(f"Error during compression: {str(e)}")
            self._compressed_output = input_file  # Fallback to uncompressed
            self.compressionFinished.emit()
            return False
    
    @pyqtSlot(result=bool)
    def copyTrimToClipboard(self):
        """Copy the trimmed video file path to clipboard so it can be pasted into applications"""
        if not self._trim_completed:
            self.errorOccurred.emit("No trimmed video available")
            return False
            
        try:
            # Use the compressed version if available, otherwise use the trimmed version
            file_to_copy = self._compressed_output if self._compressed_output else self._temp_output
            
            if not os.path.exists(file_to_copy):
                self.errorOccurred.emit("Trimmed video file not found")
                return False
            
            # Schedule the clipboard operation to run asynchronously
            QTimer.singleShot(100, lambda: self._copy_file_path_to_clipboard(file_to_copy))
            
            # Get file size for display
            file_size_mb = os.path.getsize(file_to_copy) / (1024 * 1024)
            self.trimCompleteChanged.emit(f"Video copied to clipboard ({file_size_mb:.1f}MB)")
            return True
        except Exception as e:
            self.errorOccurred.emit(f"Error preparing video: {str(e)}")
            return False
    
    def _copy_file_path_to_clipboard(self, file_path):
        """Copy the file path to clipboard for file drops"""
        try:
            # Check if wl-copy is available (for Wayland)
            if not shutil.which("wl-copy"):
                self.errorOccurred.emit("wl-clipboard not installed. Install with: sudo pacman -S wl-clipboard")
                return
                
            # Copy the file itself, not just its name
            # Use -t option to set the MIME type as text/uri-list for file paths
            cmd = ['wl-copy', '-t', 'text/uri-list', f"file://{file_path}"]
            subprocess.run(cmd, timeout=2)
            
            # Also copy the file path as plain text as a fallback
            cmd = ['wl-copy', '-p', file_path]  # -p for primary selection
            subprocess.run(cmd, timeout=2)
            
        except Exception as e:
            self.errorOccurred.emit(f"Clipboard operation error: {str(e)}")
    
    @pyqtSlot(result=bool)
    def saveTrimmingDialog(self):
        """Save the trimmed video using KDE's native file dialog"""
        if not self._trim_completed:
            self.errorOccurred.emit("No trimmed video available")
            return False
            
        try:
            # Use the compressed version if available, otherwise use the trimmed version
            file_to_save = self._compressed_output if self._compressed_output else self._temp_output
            
            if not os.path.exists(file_to_save):
                self.errorOccurred.emit("Trimmed video file not found")
                return False
                
            # Use KDE's native file dialog through kdialog command
            original_filename = os.path.basename(self._video_path)
            extension = os.path.splitext(original_filename)[1]
            output_path = os.path.join(os.path.expanduser("~"), f"trimmed_{original_filename}")
            
            cmd = [
                'kdialog', 
                '--getsavefilename', 
                output_path,
                f'Video files (*{extension})'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                # Copy the file to the selected location
                output_path = result.stdout.strip()
                shutil.copy2(file_to_save, output_path)
                
                # Get file size for display
                file_size_mb = os.path.getsize(file_to_save) / (1024 * 1024)
                self.trimCompleteChanged.emit(f"Saved to: {output_path} ({file_size_mb:.1f}MB)")
                return True
            else:
                # User cancelled or error
                return False
                
        except Exception as e:
            self.errorOccurred.emit(f"Error saving file: {str(e)}")
            return False


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='OTrimmer - KDE Wayland video trimmer')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('video_file', nargs='?', help='Path to the video file to trim')
    group.add_argument('-g', '--gallery', action='store_true', help='Open gallery view of videos in current directory')
    args = parser.parse_args()
    
    # Set up QUrl handling for Windows paths if needed
    QUrl.setPath = getattr(QUrl, 'setPath', lambda self, path: self)
    
    # Set environment variables for QML
    os.environ["QML_XHR_ALLOW_FILE_READ"] = "1"
    
    # Set up application
    app = QGuiApplication(sys.argv)
    app.setApplicationName("OTrimmer")
    app.setOrganizationName("KDE")
    
    # Set environment variables for Kirigami and GStreamer
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "org.kde.desktop"
    # Use wayland if available, otherwise fall back to xcb
    if "WAYLAND_DISPLAY" in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "wayland"
    else:
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    
    # Set additional Kirigami environment variables
    os.environ["QT_QUICK_CONTROLS_MOBILE"] = "false"
    os.environ["QT_LOGGING_RULES"] = "kf.kirigami.warning=false"
    
    # Register types for QML
    qmlRegisterType(VideoTrimmer, "Trimmer", 1, 0, "VideoTrimmer")
    qmlRegisterType(VideoGallery, "Trimmer", 1, 0, "VideoGallery")
    
    # Set additional QML import paths for Kirigami
    import_paths = [
        "/usr/lib/qt/qml",
        "/usr/lib/qt5/qml",
        "/usr/share/qt5/qml",
        os.path.expanduser("~/.local/lib/qt/qml")
    ]
    
    # Find the QML files - could be in multiple locations
    qml_root_path = None
    potential_root_paths = [
        # Check in the same directory as the script
        os.path.dirname(os.path.abspath(__file__)),
        # Check in standard KDE application data paths
        "/usr/share/trimmer",
        os.path.expanduser("~/.local/share/trimmer")
    ]
    
    for path in potential_root_paths:
        if os.path.exists(path):
            qml_root_path = path
            break
    
    if not qml_root_path:
        print("Error: Could not find application data directory")
        sys.exit(1)
    
    qml_file = None
    if args.gallery:
        qml_file = os.path.join(qml_root_path, "gallery.qml")
        # Fall back to the embedded resource if the file doesn't exist
        if not os.path.exists(qml_file):
            # Create the gallery QML file if it doesn't exist
            gallery_qml_content = GALLERY_QML_CONTENT
            os.makedirs(os.path.dirname(qml_file), exist_ok=True)
            with open(qml_file, 'w') as f:
                f.write(gallery_qml_content)
    else:
        qml_file = os.path.join(qml_root_path, "otrimmer.qml")
        # Fall back to the embedded resource if the file doesn't exist
        if not os.path.exists(qml_file):
            qml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "otrimmer.qml")
    
    if not os.path.exists(qml_file):
        print(f"Error: Could not find QML file at {qml_file}")
        sys.exit(1)
    
    # Create the engine
    engine = QQmlApplicationEngine()
    
    # Add import paths
    for path in import_paths:
        engine.addImportPath(path)
    
    # Set context properties
    context = engine.rootContext()
    
    if args.gallery:
        # Open gallery view
        gallery = VideoGallery()
        context.setContextProperty("gallery", gallery)
        context.setContextProperty("initialDirectory", os.getcwd())
    else:
        # Trim specific video file
        if not args.video_file:
            print("Error: No video file specified. Use -g/--gallery to browse videos.")
            parser.print_help()
            sys.exit(1)
            
        video_path = args.video_file
        if not os.path.exists(video_path):
            print(f"Error: File '{video_path}' not found")
            sys.exit(1)
            
        # Convert to absolute path
        abs_video_path = os.path.abspath(video_path)
        url = QUrl.fromLocalFile(abs_video_path)
        
        context.setContextProperty("initialVideoPath", url)
        context.setContextProperty("initialVideoPathString", abs_video_path)
    
    # Load the QML file
    engine.load(QUrl.fromLocalFile(qml_file))
    
    if not engine.rootObjects():
        print(f"Error: Failed to load QML from {qml_file}")
        sys.exit(1)
    
    sys.exit(app.exec_())

# Gallery QML template - will be saved to disk if not found
GALLERY_QML_CONTENT = """import QtQuick 2.15
import QtQuick.Controls 2.15 as Controls
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.19 as Kirigami
import QtQuick.Window 2.15
import Trimmer 1.0

Kirigami.ApplicationWindow {
    id: root
    width: 900
    height: 600
    title: "OTrimmer Gallery"
    
    // Gallery model
    VideoGallery {
        id: gallery
        
        Component.onCompleted: {
            loadFromDirectory(initialDirectory)
        }
        
        onVideoSelected: function(filepath) {
            console.log("Video selected: " + filepath);
            
            // Let the Python backend handle launching the video trimmer
            gallery.openVideoInTrimmer(filepath);
            
            // Note: The Python side will handle quitting after launching the new process
        }
    }
    
    // Global theme settings
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None
    pageStack.defaultColumnWidth: root.width
    
    // Notifications
    Kirigami.InlineMessage {
        id: errorNotification
        visible: false
        type: Kirigami.MessageType.Error
        text: ""
        anchors {
            top: parent.top
            left: parent.left
            right: parent.right
            margins: Kirigami.Units.largeSpacing
        }
        z: 999
    }
    
    // Main page
    pageStack.initialPage: Kirigami.Page {
        padding: 0
        
        ColumnLayout {
            anchors.fill: parent
            spacing: 0
            
            // Toolbar
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: toolbarLayout.height + Kirigami.Units.largeSpacing * 2
                color: Kirigami.Theme.highlightColor
                
                RowLayout {
                    id: toolbarLayout
                    anchors {
                        left: parent.left
                        right: parent.right
                        top: parent.top
                        margins: Kirigami.Units.largeSpacing
                    }
                    
                    Kirigami.Heading {
                        level: 1
                        text: "Video Gallery"
                        color: Kirigami.Theme.highlightedTextColor
                    }
                    
                    Item { Layout.fillWidth: true }
                    
                    Controls.ComboBox {
                        id: sortComboBox
                        model: ["Name", "Size", "Date Modified"]
                        
                        onActivated: {
                            switch (currentIndex) {
                                case 0: // Name
                                    if (sortOrderToggle.checked) {
                                        gallery.sortByDescending(gallery.filenameRole)
                                    } else {
                                        gallery.sortBy(gallery.filenameRole)
                                    }
                                    break
                                case 1: // Size
                                    if (sortOrderToggle.checked) {
                                        gallery.sortByDescending(gallery.filesizeRole)
                                    } else {
                                        gallery.sortBy(gallery.filesizeRole)
                                    }
                                    break
                                case 2: // Date Modified
                                    if (sortOrderToggle.checked) {
                                        gallery.sortByDescending(gallery.lastModifiedRole)
                                    } else {
                                        gallery.sortBy(gallery.lastModifiedRole)
                                    }
                                    break
                            }
                        }
                    }
                    
                    Controls.ToolButton {
                        id: sortOrderToggle
                        icon.name: checked ? "sort-name-descending" : "sort-name-ascending"
                        checkable: true
                        
                        onToggled: {
                            // Re-sort based on current combo box selection
                            sortComboBox.activated(sortComboBox.currentIndex)
                        }
                    }
                    
                    Controls.Slider {
                        id: thumbnailSizeSlider
                        from: 120
                        to: 240
                        stepSize: 20
                        value: 160
                        Layout.preferredWidth: 100
                    }
                }
            }
            
            // Gallery view - Grid Layout
            Controls.ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                
                GridView {
                    id: galleryGrid
                    model: gallery.model
                    
                    // Force model to be evaluated only after it's ready
                    Component.onCompleted: {
                        // This ensures the model is properly processed
                        console.log("Grid view initialized with " + count + " items")
                    }
                    cellWidth: thumbnailSizeSlider.value + Kirigami.Units.largeSpacing
                    cellHeight: thumbnailSizeSlider.value + 40 // Extra space for caption
                    
                    delegate: Item {
                        width: galleryGrid.cellWidth
                        height: galleryGrid.cellHeight
                        
                        // Thumbnail container with hover effect
                        Rectangle {
                            id: thumbnailContainer
                            anchors.centerIn: parent
                            width: thumbnailSizeSlider.value
                            height: thumbnailSizeSlider.value
                            color: "black"
                            border.width: mouseArea.containsMouse ? 3 : 1
                            border.color: mouseArea.containsMouse ? Kirigami.Theme.highlightColor : Kirigami.Theme.disabledTextColor
                            radius: 5
                            
                            // Video thumbnail
                            Image {
                                id: thumbnail
                                anchors.fill: parent
                                anchors.margins: 2
                                source: model.thumbnailPath || "qrc:///icons/video-x-generic"
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                                
                                // Placeholder while loading
                                Rectangle {
                                    anchors.fill: parent
                                    color: Kirigami.Theme.backgroundColor
                                    visible: thumbnail.status !== Image.Ready
                                    
                                    Kirigami.Icon {
                                        anchors.centerIn: parent
                                        source: "video-x-generic"
                                        width: 48
                                        height: 48
                                    }
                                }
                                
                                // Play icon overlay
                                Kirigami.Icon {
                                    anchors.centerIn: parent
                                    source: "media-playback-start"
                                    width: 32
                                    height: 32
                                    color: "white"
                                    opacity: mouseArea.containsMouse ? 1.0 : 0.7
                                    visible: mouseArea.containsMouse
                                }
                            }
                            
                            // File size indicator
                            Rectangle {
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                anchors.margins: 4
                                width: sizeLabel.width + 10
                                height: sizeLabel.height + 6
                                color: "#80000000"
                                radius: 3
                                
                                Controls.Label {
                                    id: sizeLabel
                                    anchors.centerIn: parent
                                    text: model.fileSizeFormatted
                                    color: "white"
                                    font.pointSize: 8
                                }
                            }
                        }
                        
                        // Filename below thumbnail
                        Controls.Label {
                            anchors.top: thumbnailContainer.bottom
                            anchors.horizontalCenter: thumbnailContainer.horizontalCenter
                            anchors.topMargin: 4
                            text: model.filename
                            width: thumbnailContainer.width
                            elide: Text.ElideMiddle
                            horizontalAlignment: Text.AlignHCenter
                            font.pointSize: 9
                        }
                        
                        // Mouse interaction area
                        MouseArea {
                            id: mouseArea
                            anchors.fill: parent
                            hoverEnabled: true
                            
                            // Show detailed tooltip on hover
                            Controls.ToolTip {
                                visible: mouseArea.containsMouse
                                delay: 500
                                timeout: 5000
                                
                                contentItem: ColumnLayout {
                                    spacing: 4
                                    
                                    Controls.Label {
                                        text: "<b>" + model.filename + "</b>"
                                        wrapMode: Text.WordWrap
                                        Layout.maximumWidth: 300
                                    }
                                    
                                    Controls.Label {
                                        text: "<b>Size:</b> " + model.fileSizeFormatted
                                    }
                                    
                                    Controls.Label {
                                        text: "<b>Modified:</b> " + Qt.formatDateTime(model.lastModified, "yyyy-MM-dd hh:mm")
                                    }
                                    
                                    Controls.Label {
                                        text: "<b>Path:</b> " + model.filepath
                                        elide: Text.ElideMiddle
                                        Layout.maximumWidth: 300
                                    }
                                }
                            }
                            
                            onClicked: {
                                // Select when clicking anywhere on the item
                                console.log("Opening video: " + model.filepath);
                                // Call the Python method directly
                                gallery.openVideoInTrimmer(model.filepath);
                            }
                        }
                    }
                    
                    // Empty state
                    Controls.Pane {
                        anchors.centerIn: parent
                        visible: galleryGrid.count === 0
                        
                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: Kirigami.Units.largeSpacing
                            
                            Kirigami.Icon {
                                source: "folder-videos"
                                implicitWidth: Kirigami.Units.iconSizes.huge
                                implicitHeight: Kirigami.Units.iconSizes.huge
                                Layout.alignment: Qt.AlignHCenter
                            }
                            
                            Controls.Label {
                                text: "No video files found"
                                font.bold: true
                                Layout.alignment: Qt.AlignHCenter
                            }
                            
                            Controls.Label {
                                text: "Try a different directory or add some videos"
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }
                }
            }
            
            // Status bar
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: statusLayout.height + Kirigami.Units.smallSpacing * 2
                color: Kirigami.Theme.backgroundColor
                
                RowLayout {
                    id: statusLayout
                    anchors {
                        left: parent.left
                        right: parent.right
                        verticalCenter: parent.verticalCenter
                        margins: Kirigami.Units.smallSpacing
                    }
                    
                    Controls.Label {
                        text: galleryGrid.count + " videos found in " + initialDirectory
                        Layout.fillWidth: true
                        elide: Text.ElideMiddle
                    }
                    
                    Controls.Button {
                        text: "Refresh"
                        icon.name: "view-refresh"
                        onClicked: gallery.loadFromDirectory(initialDirectory)
                    }
                }
            }
        }
    }
    
    // Get the application directory for launching the trimmer
    readonly property string applicationDirPath: {
        // Extract the application directory from the QML file path
        var path = Qt.resolvedUrl(".")
        path = path.replace("file://", "")
        path = path.substring(0, path.lastIndexOf("/"))
        return path
    }
    
    Component.onCompleted: {
        console.log("Gallery started")
        console.log("Looking for videos in: " + initialDirectory)
        
        // Small delay to ensure the UI is ready before loading data
        loadTimer.start()
    }
    
    Timer {
        id: loadTimer
        interval: 100
        repeat: false
        onTriggered: {
            // Set initial sort (by name)
            gallery.sortBy(gallery.filenameRole)
        }
    }
}
"""

if __name__ == "__main__":
    main()