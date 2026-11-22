import QtQuick

// 主按钮：按下回弹 + 悬停微放大
Rectangle {
    id: btn

    property string text: "按钮"
    property bool primary: true
    property bool active: true
    property int fontSize: 14

    signal clicked()

    // 悬停状态外露，供按钮文案随悬停切换（例如「游戏运行中」→「结束游戏」）
    readonly property bool hovered: mouse.containsMouse

    implicitHeight: 40
    implicitWidth: labelText.implicitWidth + 44
    radius: height / 2

    readonly property color fillColor: primary
                                       ? theme.accent
                                       : (btn.pressedHover ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.14)
                                                           : "transparent")
    readonly property color labelColor: primary ? theme.onAccent
                                                 : (btn.pressedHover ? theme.accent : theme.text2)
    readonly property bool pressedHover: mouse.containsMouse && active
    readonly property color strokeColor: primary
                                         ? "transparent"
                                         : (btn.pressedHover ? theme.accent
                                                             : Qt.rgba(theme.border.r, theme.border.g, theme.border.b, 0.9))

    color: fillColor
    border.width: primary ? 0 : 1
    border.color: strokeColor
    Behavior on border.color { ColorAnimation { duration: 160 } }
    opacity: active ? 1.0 : 0.45
    scale: (mouse.pressed && active) ? 0.955 : ((mouse.containsMouse && active) ? 1.028 : 1.0)

    // 弹簧代替匀速缓动：按下与松开带轻微过冲，手感更弹
    Behavior on scale {
        SpringAnimation { spring: 4.6; damping: 0.42; epsilon: 0.001 }
    }
    Behavior on opacity {
        NumberAnimation { duration: 160 }
    }
    Behavior on color {
        ColorAnimation { duration: 200 }
    }

    // ------------------------------------------------ 点击涟漪
    property real rippleCx: width / 2
    property real rippleCy: height / 2
    property real rippleDia: 0
    readonly property real rippleMax: Math.max(width, height) * 1.9

    function burst(px, py) {
        rippleCx = px;
        rippleCy = py;
        rippleDia = 0;
        rippleAnim.restart();
    }

    Rectangle {
        anchors.fill: parent
        radius: btn.radius
        color: "transparent"
        clip: true

        Rectangle {
            id: rippleRect
            width: btn.rippleDia
            height: btn.rippleDia
            radius: btn.rippleDia / 2
            x: btn.rippleCx - btn.rippleDia / 2
            y: btn.rippleCy - btn.rippleDia / 2
            color: btn.primary
                   ? Qt.rgba(1, 1, 1, 0.55)
                   : Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.30)
            opacity: 0

            SequentialAnimation {
                id: rippleAnim
                PropertyAction { target: rippleRect; property: "opacity"; value: 0.85 }
                ParallelAnimation {
                    NumberAnimation {
                        target: btn; property: "rippleDia"
                        from: 0; to: btn.rippleMax
                        duration: 520; easing.type: Easing.OutCubic
                    }
                    NumberAnimation {
                        target: rippleRect; property: "opacity"
                        to: 0; duration: 520; easing.type: Easing.OutQuad
                    }
                }
            }
        }
    }

    Text {
        id: labelText
        anchors.centerIn: parent
        text: btn.text
        color: btn.labelColor
        font.pixelSize: btn.fontSize
        font.weight: Font.Medium
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: btn.active ? Qt.PointingHandCursor : Qt.ArrowCursor
        onPressed: if (btn.active) btn.burst(mouse.x, mouse.y)
        onClicked: if (btn.active) btn.clicked()
    }
}
