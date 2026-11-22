import QtQuick

// 柔和光晕：多层同心圆模拟径向渐变，比高斯模糊更轻、任何渲染后端都稳定
Item {
    id: glow

    property color glowColor: "#7BC96F"
    property real diameter: 620
    property real intensity: 0.30
    property int layers: 7
    property real driftX: 0
    property real driftY: 0
    property real breath: 1.0
    // 鼠标视差：外层写入，值本身已做弹性平滑，这里只叠加
    property real parallaxX: 0
    property real parallaxY: 0

    implicitWidth: diameter
    implicitHeight: diameter
    opacity: intensity
    scale: breath
    x: driftX + parallaxX
    y: driftY + parallaxY

    Repeater {
        model: glow.layers

        Rectangle {
            required property int index
            readonly property real t: index / Math.max(1, glow.layers - 1)
            width: glow.diameter * (1.0 - t * 0.72)
            height: width
            radius: width / 2
            anchors.centerIn: parent
            color: glow.glowColor
            opacity: 0.13 + (1.0 - t) * 0.16
        }
    }

    Behavior on opacity {
        NumberAnimation { duration: 420; easing.type: Easing.OutCubic }
    }
}
