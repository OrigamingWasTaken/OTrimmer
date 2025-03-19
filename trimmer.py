#!/usr/bin/env python3

import sys
import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, pyqtProperty, QUrl, QTimer
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtQml import QQmlApplicationEngine, qmlRegisterType, QQmlEngine
from PyQt5.QtQuick import QQuickView
import PyQt5

class VideoTrimmer(QObject):
    startTimeChanged = pyqtSignal()
    endTimeChanged = pyqtSignal()
    durationChanged = pyqtSignal()
    trimCompleteChanged = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)
    compressionProgressChanged = pyqtSignal(int)  # For progress updates

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
    # Get video path from command line
    if len(sys.argv) < 2:
        print("Usage: trimmer <video_file>")
        sys.exit(1)
        
    video_path = sys.argv[1]
    if not os.path.exists(video_path):
        print(f"Error: File '{video_path}' not found")
        sys.exit(1)
    
    # Set up application
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Trimmer")
    app.setOrganizationName("KDE")
    
    # Set environment variables for Kirigami and GStreamer
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "org.kde.desktop"
    os.environ["QT_QPA_PLATFORM"] = "xcb"
    
    # Register the VideoTrimmer type for QML
    qmlRegisterType(VideoTrimmer, "Trimmer", 1, 0, "VideoTrimmer")
    
    # Create the engine
    engine = QQmlApplicationEngine()
    
    # Set additional QML import paths for Kirigami
    import_paths = engine.importPathList()
    import_paths.append("/usr/lib/qt/qml")
    import_paths.append("/usr/lib/qt5/qml")
    import_paths.append("/usr/share/qt5/qml")
    import_paths.append(os.path.expanduser("~/.local/lib/qt/qml"))
    engine.setImportPathList(import_paths)
    
    # Load QML
    engine = QQmlApplicationEngine()
    
    # Find the QML file - could be in multiple locations
    qml_file = None
    potential_paths = [
        # Check in the same directory as the script
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "trimmer.qml"),
        # Check in standard KDE application data paths
        "/usr/share/trimmer/trimmer.qml",
        os.path.expanduser("~/.local/share/trimmer/trimmer.qml")
    ]
    
    for path in potential_paths:
        if os.path.exists(path):
            qml_file = path
            break
    
    if not qml_file:
        print("Error: Could not find trimmer.qml")
        sys.exit(1)
    
    # Pass the video path to QML
    # Convert to absolute path
    abs_video_path = os.path.abspath(video_path)
    url = QUrl.fromLocalFile(abs_video_path)
    
    context = engine.rootContext()
    context.setContextProperty("initialVideoPath", url)
    context.setContextProperty("initialVideoPathString", abs_video_path)
    
    engine.load(QUrl.fromLocalFile(qml_file))
    
    if not engine.rootObjects():
        print("Error: Failed to load QML")
        sys.exit(1)
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
