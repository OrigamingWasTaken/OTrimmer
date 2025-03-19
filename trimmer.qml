import QtQuick 2.15
import QtQuick.Controls 2.15 as Controls
import QtQuick.Layouts 1.15
import QtMultimedia 5.15
import org.kde.kirigami 2.19 as Kirigami
import QtQuick.Window 2.15
import Trimmer 1.0
import QtQuick.Dialogs 1.3

Kirigami.ApplicationWindow {
    id: root
    width: 900
    height: 600
    title: "OTrimmer"
    
    // Video trimming state
    property bool trimComplete: false
    property bool isDarkTheme: Kirigami.Theme.colorSet === Kirigami.Theme.Dark
    
    // Video trimmer backend
    VideoTrimmer {
        id: trimmer
        
        onTrimCompleteChanged: function(message) {
            trimComplete = true
            successNotification.text = message
            successNotification.visible = true
            hideTimer.restart()
        }
        
        onErrorOccurred: function(message) {
            errorNotification.text = message
            errorNotification.visible = true
            hideTimer.restart()
        }
    }
    
    // Timer to hide notifications
    Timer {
        id: hideTimer
        interval: 3000
        onTriggered: {
            successNotification.visible = false
            errorNotification.visible = false
        }
    }
    
    // Global theme settings
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None
    pageStack.defaultColumnWidth: root.width
    
    // Notifications
    Kirigami.InlineMessage {
        id: successNotification
        visible: false
        type: Kirigami.MessageType.Positive
        text: ""
        anchors {
            top: parent.top
            left: parent.left
            right: parent.right
            margins: Kirigami.Units.largeSpacing
        }
        z: 999
    }
    
    Kirigami.InlineMessage {
        id: errorNotification
        visible: false
        type: Kirigami.MessageType.Error
        text: ""
        anchors {
            top: successNotification.bottom
            left: parent.left
            right: parent.right
            margins: Kirigami.Units.largeSpacing
        }
        z: 999
    }
    
    // Custom timeline component with thumbnails and trim handles
    component VideoTimeline: Item {
        id: timeline
        height: 80
        
        property int duration: 0
        property int position: 0
        property int startTime: 0
        property int endTime: duration
        property bool trimComplete: false
        
        signal startPositionRequested(int value)
        signal endPositionRequested(int value)
        signal positionRequested(int value)
        
        // Background
        Rectangle {
            id: background
            anchors.fill: parent
            color: Kirigami.Theme.backgroundColor
            opacity: 0.3
            radius: 4
        }
        
        // Thumbnails (simulated - in a real app, these would be actual video frames)
        Row {
            id: thumbnails
            anchors.fill: parent
            anchors.margins: 2
            
            Repeater {
                model: 10
                
                Rectangle {
                    width: parent.width / 10
                    height: parent.height
                    color: Kirigami.Theme.backgroundColor
                    border.width: 1
                    border.color: Kirigami.Theme.textColor
                    opacity: 0.7
                    
                    // Simulate a thumbnail
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 2
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: index % 2 == 0 ? "#80505050" : "#80606060" }
                            GradientStop { position: 1.0; color: index % 2 == 0 ? "#80606060" : "#80505050" }
                        }
                    }
                    
                    // Simulate timecode
                    Text {
                        anchors.centerIn: parent
                        color: Kirigami.Theme.textColor
                        text: formatTime((timeline.duration / 10) * index)
                        
                        function formatTime(ms) {
                            var seconds = Math.floor(ms / 1000)
                            var minutes = Math.floor(seconds / 60)
                            seconds = seconds % 60
                            return minutes.toString().padStart(2, '0') + ":" + seconds.toString().padStart(2, '0')
                        }
                    }
                }
            }
        }
        
        // Selected area overlay
        Rectangle {
            x: (timeline.startTime / timeline.duration) * parent.width
            width: ((timeline.endTime - timeline.startTime) / timeline.duration) * parent.width
            height: parent.height
            color: timeline.trimComplete ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.highlightColor
            opacity: 0.3
            visible: timeline.duration > 0
            z: 1
        }
        
        // Start handle
        Rectangle {
            id: startHandle
            x: (timeline.startTime / timeline.duration) * parent.width - width/2
            width: 10
            height: parent.height
            color: Kirigami.Theme.highlightColor
            border.width: 1
            border.color: Kirigami.Theme.highlightedTextColor
            visible: timeline.duration > 0
            z: 3
            
            // Start handle drag area
            MouseArea {
                anchors.fill: parent
                anchors.margins: -5
                drag {
                    target: parent
                    axis: Drag.XAxis
                    minimumX: -parent.width/2
                    maximumX: endHandle.x - parent.width/2
                }
                
                onPositionChanged: {
                    if (drag.active) {
                        var newStartTime = Math.max(0, (startHandle.x + startHandle.width/2) / timeline.width * timeline.duration)
                        timeline.startPositionRequested(newStartTime)
                    }
                }
            }
            
            // Visual indicator line
            Rectangle {
                width: 2
                height: parent.height
                anchors.centerIn: parent
                color: Kirigami.Theme.highlightedTextColor
            }
        }
        
        // End handle
        Rectangle {
            id: endHandle
            x: (timeline.endTime / timeline.duration) * parent.width - width/2
            width: 10
            height: parent.height
            color: Kirigami.Theme.highlightColor
            border.width: 1
            border.color: Kirigami.Theme.highlightedTextColor
            visible: timeline.duration > 0
            z: 3
            
            // End handle drag area
            MouseArea {
                anchors.fill: parent
                anchors.margins: -5
                drag {
                    target: parent
                    axis: Drag.XAxis
                    minimumX: startHandle.x + startHandle.width
                    maximumX: timeline.width - parent.width/2
                }
                
                onPositionChanged: {
                    if (drag.active) {
                        var newEndTime = Math.min(timeline.duration, (endHandle.x + endHandle.width/2) / timeline.width * timeline.duration)
                        timeline.endPositionRequested(newEndTime)
                    }
                }
            }
            
            // Visual indicator line
            Rectangle {
                width: 2
                height: parent.height
                anchors.centerIn: parent
                color: Kirigami.Theme.highlightedTextColor
            }
        }
        
        // Playhead
        Rectangle {
            id: playhead
            x: (timeline.position / timeline.duration) * parent.width - width/2
            width: 4
            height: parent.height
            color: "white"
            border.width: 1
            border.color: "black"
            visible: timeline.duration > 0
            z: 4
        }
        
        // Timeline scrub area
        MouseArea {
            anchors.fill: parent
            onClicked: {
                var newPosition = Math.max(0, Math.min(timeline.duration, (mouseX / width) * timeline.duration))
                timeline.positionRequested(newPosition)
            }
        }
    }
    
    // Main page
    pageStack.initialPage: Kirigami.Page {
        padding: 0
        
        // Video component
        MediaPlayer {
            id: mediaPlayer
            source: initialVideoPath
            autoPlay: false
            
            onStatusChanged: {
                if (status === MediaPlayer.Loaded) {
                    console.log("Media loaded successfully: " + source)
                    trimmer.setVideoFile(initialVideoPathString)
                } else if (status === MediaPlayer.InvalidMedia) {
                    console.error("Invalid media: " + source)
                    errorNotification.text = "Invalid media format or file not accessible"
                    errorNotification.visible = true
                } else if (status === MediaPlayer.NoMedia) {
                    console.log("No media loaded")
                } else if (status === MediaPlayer.Loading) {
                    console.log("Media loading...")
                }
            }
            
            onError: {
                console.error("Media player error: " + errorString)
                errorNotification.text = "Media error: " + errorString
                errorNotification.visible = true
            }
        }
        
        ColumnLayout {
            anchors.fill: parent
            spacing: 0
            
            // Toolbar
            Kirigami.Heading {
                level: 1
                text: initialVideoPath ? "Trimming: " + initialVideoPath.toString().split('/').pop() : "Video Trimmer"
                elide: Text.ElideMiddle
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.largeSpacing
            }
            
            // Video display
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.margins: Kirigami.Units.largeSpacing
                color: "black"
                
                VideoOutput {
                    id: videoOutput
                    anchors.fill: parent
                    source: mediaPlayer
                    
                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            if (mediaPlayer.playbackState === MediaPlayer.PlayingState)
                                mediaPlayer.pause()
                            else
                                mediaPlayer.play()
                        }
                    }
                }
                
                // Play button overlay (shows when paused)
                Rectangle {
                    anchors.centerIn: parent
                    width: 60
                    height: 60
                    radius: 30
                    color: "#80000000"
                    visible: mediaPlayer.playbackState !== MediaPlayer.PlayingState
                    
                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: 32
                        height: 32
                        source: "media-playback-start"
                        color: "white"
                    }
                }
            }
            
            // Video timeline
            VideoTimeline {
                id: videoTimeline
                Layout.fillWidth: true
                Layout.preferredHeight: 80
                Layout.margins: Kirigami.Units.largeSpacing
                
                duration: trimmer.duration
                position: mediaPlayer.position
                startTime: trimmer.startTime
                endTime: trimmer.endTime
                trimComplete: root.trimComplete
                
                onStartPositionRequested: {
                    trimmer.startTime = value
                    root.trimComplete = false
                }
                
                onEndPositionRequested: {
                    trimmer.endTime = value
                    root.trimComplete = false
                }
                
                onPositionRequested: {
                    mediaPlayer.seek(value)
                }
            }
            
            // Playback controls
            RowLayout {
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.largeSpacing
                
                Controls.Button {
                    icon.name: mediaPlayer.playbackState === MediaPlayer.PlayingState ? "media-playback-pause" : "media-playback-start"
                    text: mediaPlayer.playbackState === MediaPlayer.PlayingState ? "Pause" : "Play"
                    onClicked: {
                        if (mediaPlayer.playbackState === MediaPlayer.PlayingState)
                            mediaPlayer.pause()
                        else
                            mediaPlayer.play()
                    }
                }
                
                Controls.Label {
                    text: formatTime(mediaPlayer.position) + " / " + formatTime(trimmer.duration)
                    
                    function formatTime(ms) {
                        var seconds = Math.floor(ms / 1000)
                        var minutes = Math.floor(seconds / 60)
                        seconds = seconds % 60
                        return minutes.toString().padStart(2, '0') + ":" + seconds.toString().padStart(2, '0')
                    }
                }
                
                Controls.Label {
                    text: "Selection: " + formatTime(trimmer.endTime - trimmer.startTime)
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    
                    function formatTime(ms) {
                        var seconds = Math.floor(ms / 1000)
                        var minutes = Math.floor(seconds / 60)
                        seconds = seconds % 60
                        return minutes.toString().padStart(2, '0') + ":" + seconds.toString().padStart(2, '0')
                    }
                }
                
                RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    
                    Controls.Button {
                        text: "Trim"
                        icon.name: "edit-cut"
                        enabled: !root.trimComplete && trimmer.startTime < trimmer.endTime
                        
                        onClicked: {
                            trimmer.createTrim()
                            root.trimComplete = true
                        }
                    }
                    
                    Controls.Button {
                        text: "Copy to Clipboard"
                        icon.name: "edit-copy"
                        enabled: root.trimComplete
                        
                        onClicked: {
                            trimmer.copyTrimToClipboard()
                        }
                    }
                    
                    Controls.Button {
                        text: "Save"
                        icon.name: "document-save"
                        enabled: root.trimComplete
                        
                        onClicked: {
                            trimmer.saveTrimmingDialog()
                        }
                    }
                }
            }
        }
    }
    
    Component.onCompleted: {
        console.log("Application started")
        console.log("Initial video path: " + initialVideoPath)
        
        if (initialVideoPath) {
            // Call setVideoFile directly to set up the backend
            trimmer.setVideoFile(initialVideoPathString)
            
            // Small delay to ensure UI is ready before trying to load the video
            loadTimer.start()
        }
    }
    
    Timer {
        id: loadTimer
        interval: 500
        repeat: false
        onTriggered: {
            mediaPlayer.source = initialVideoPath
            mediaPlayer.pause()
        }
    }
}