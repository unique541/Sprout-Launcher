import QtQuick

// 侧边导航项：选中时左侧指示条弹性滑入 + 底色渐显
Item {
    id: nav

    property string label: ""
    property string icon: ""
    property bool active: false

    signal activated()

    implicitHeight: 46
    implicitWidth: 200

    Rectangle {
        id: pill
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        radius: 12
        color: theme.accentSoft
        // 选中态由外层滑动高亮承担，这里只负责悬停反馈
        opacity: nav.active ? 0.0 : (mouse.containsMouse ? 0.5 : 0.0)

        Behavior on opacity {
            NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
        }
    }

    Rectangle {
        id: indicator
        width: 3
        height: nav.active ? 20 : 6
        radius: 2
        color: theme.accent
        anchors.left: parent.left
        anchors.leftMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        opacity: nav.active ? 1.0 : (mouse.containsMouse ? 0.5 : 0.0)

        Behavior on height {
            NumberAnimation { duration: 240; easing.type: Easing.OutBack; easing.overshoot: 1.6 }
        }
        Behavior on opacity {
            NumberAnimation { duration: 180 }
        }
    }

    Row {
        id: navRow
        x: 26 + (nav.active ? 2 : (mouse.containsMouse ? 4 : 0))
        y: (nav.height - height) / 2
        spacing: 12

        Behavior on x {
            SpringAnimation { spring: 4.2; damping: 0.45; epsilon: 0.001 }
        }

        Text {
            text: nav.icon
            width: 18
            horizontalAlignment: Text.AlignHCenter
            font.pixelSize: 16
            font.family: "Segoe UI Symbol"
            renderType: Text.NativeRendering
            anchors.verticalCenter: parent.verticalCenter
            opacity: nav.active ? 1.0 : 0.62
            Behavior on opacity { NumberAnimation { duration: 180 } }
        }

        Text {
            text: nav.label
            font.pixelSize: 14
            font.weight: nav.active ? Font.DemiBold : Font.Normal
            color: nav.active ? theme.accent : theme.text2
            anchors.verticalCenter: parent.verticalCenter
            Behavior on color { ColorAnimation { duration: 180 } }
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: nav.activated()
    }
}
