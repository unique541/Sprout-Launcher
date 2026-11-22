import QtQuick

// 卡片容器：hover 时轻微抬升 + 边框高亮，全程走插值动画
Rectangle {
    id: card

    property bool interactive: true
    property bool hovered: hoverArea.containsMouse
    property color baseColor: theme.card
    property color lineColor: theme.border
    property real hoverLift: 2
    property real corner: 14

    radius: corner
    color: baseColor
    border.width: 1
    border.color: hovered && interactive ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.55) : lineColor

    scale: hovered && interactive ? 1.008 : 1.0
    y: hovered && interactive ? -hoverLift : 0

    Behavior on scale {
        NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
    }
    Behavior on y {
        NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
    }
    Behavior on border.color {
        ColorAnimation { duration: 180 }
    }

    MouseArea {
        id: hoverArea
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
    }
}
