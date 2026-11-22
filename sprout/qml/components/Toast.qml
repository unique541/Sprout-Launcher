import QtQuick

Item {
    id: toastRoot

    property string level: "info"
    property bool showing: false

    implicitWidth: bubble.implicitWidth
    implicitHeight: bubble.implicitHeight
    opacity: 0
    y: 14

    Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    Behavior on y { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }

    function show(message, lvl) {
        label.text = message;
        toastRoot.level = lvl || "info";
        toastRoot.showing = true;
        toastRoot.opacity = 1;
        toastRoot.y = 0;
        hideTimer.restart();
    }

    Timer {
        id: hideTimer
        interval: 2800
        onTriggered: {
            toastRoot.opacity = 0;
            toastRoot.y = 14;
            toastRoot.showing = false;
        }
    }

    Rectangle {
        id: bubble
        implicitWidth: row.implicitWidth + 34
        implicitHeight: 40
        radius: 10
        color: theme.dark ? theme.surfaceAlt : theme.text1
        opacity: 0.96

        Row {
            id: row
            anchors.centerIn: parent
            spacing: 10

            Rectangle {
                width: 6
                height: 6
                radius: 3
                anchors.verticalCenter: parent.verticalCenter
                color: toastRoot.level === "error" ? "#E06B6B"
                     : toastRoot.level === "warn" ? "#E5A94D"
                     : toastRoot.level === "success" ? theme.accent
                     : theme.text3
            }

            Text {
                id: label
                font.pixelSize: 13
                color: theme.dark ? theme.text1 : "#FFFFFF"
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }
}
