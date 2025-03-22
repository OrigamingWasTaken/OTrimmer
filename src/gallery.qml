import QtQuick 2.15
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
    // Note: Application icon is set in Python code
    
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
                                gallery.selectVideo(model.filepath)
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