import QtQuick

// 漂浮粒子层：纯 Rectangle 淡入上浮循环，走渲染线程，开销极低
Item {
    id: fl

    property color particleColor: "#7BC96F"
    property int count: 24
    property real maxSize: 3.2
    property real speedScale: 1.0
    property bool running: true

    Repeater {
        model: fl.count

        delegate: Item {
            id: p
            required property int index

            readonly property real seed: ((index * 37) % 89) / 89.0
            readonly property real life: (7600 + seed * 6600) / fl.speedScale

            width: 1.6 + seed * fl.maxSize
            height: width
            x: (((index * 73) % 97) / 97.0) * Math.max(1, fl.width)
            opacity: 0

            Rectangle {
                anchors.fill: parent
                radius: width / 2
                color: fl.particleColor
            }

            SequentialAnimation {
                loops: Animation.Infinite
                running: fl.running

                ParallelAnimation {
                    NumberAnimation {
                        target: p; property: "opacity"
                        from: 0; to: 0.12 + p.seed * 0.20
                        duration: p.life * 0.4
                        easing.type: Easing.InOutSine
                    }
                    NumberAnimation {
                        target: p; property: "y"
                        from: fl.height * (0.30 + p.seed * 0.70)
                        to: fl.height * (0.02 + p.seed * 0.18)
                        duration: p.life * 0.82
                        easing.type: Easing.Linear
                    }
                }

                ParallelAnimation {
                    NumberAnimation {
                        target: p; property: "opacity"
                        to: 0
                        duration: p.life * 0.26
                        easing.type: Easing.InOutSine
                    }
                    NumberAnimation {
                        target: p; property: "y"
                        to: -8
                        duration: p.life * 0.26
                        easing.type: Easing.Linear
                    }
                }
            }
        }
    }
}
