import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "components"
import "pages"

Window {
    id: root

    width: 1180
    height: 760
    minimumWidth: 1000
    minimumHeight: 660
    visible: true
    flags: Qt.Window | Qt.FramelessWindowHint
    color: "transparent"
    title: "Sprout Launcher"

    property string currentPage: "home"

    // 鼠标视差（-1 ~ 1），由 shell 内 HoverHandler 更新
    property real parX: 0
    property real parY: 0

    Behavior on parX { SpringAnimation { spring: 3.0; damping: 0.6; epsilon: 0.002 } }
    Behavior on parY { SpringAnimation { spring: 3.0; damping: 0.6; epsilon: 0.002 } }

    onCurrentPageChanged: {
        pageTitle.opacity = 0.1;
        Qt.callLater(function () { pageTitle.opacity = 1.0; });
    }

    readonly property var pageOrder: ["home", "versions", "mods", "accounts", "multiplayer",
                                      "diagnose", "console", "settings", "about"]

    readonly property int navIndex: Math.max(0, pageOrder.indexOf(currentPage))

    readonly property var pageTitles: ({
        home: "首页",
        versions: "版本库",
        mods: "模组",
        settings: "设置",
        console: "运行日志",
        accounts: "账号管理",
        multiplayer: "多人联机",
        diagnose: "自检诊断",
        about: "关于与更新"
    })

    Component {
        id: homeComp
        HomePage {
            onRequestPage: function (name, arg) {
                if (name === "mods" && arg)
                    bridge.useGameForMods(arg);
                root.navigate(name);
            }
        }
    }
    Component { id: versionsComp; VersionsPage { } }
    Component { id: modsComp; ModsPage { } }
    Component { id: settingsComp; SettingsPage { } }
    Component { id: consoleComp; ConsolePage { } }
    Component { id: accountsComp; AccountsPage { } }
    Component { id: multiplayerComp; MultiplayerPage { } }
    Component { id: diagnoseComp; DiagnosePage { } }
    Component { id: aboutComp; AboutPage { } }

    function navigate(name) {
        if (currentPage === name)
            return;
        currentPage = name;
        var map = {
            home: homeComp,
            versions: versionsComp,
            mods: modsComp,
            settings: settingsComp,
            console: consoleComp,
            accounts: accountsComp,
            multiplayer: multiplayerComp,
            diagnose: diagnoseComp,
            about: aboutComp
        };
        stack.replace(map[name]);
    }

    // 窗口整体入场
    opacity: 0
    NumberAnimation on opacity {
        from: 0
        to: 1
        duration: 380
        easing.type: Easing.OutCubic
        running: true
    }

    Rectangle {
        id: shell
        anchors.fill: parent
        radius: 16
        color: theme.bg
        clip: true
        border.width: 1
        border.color: theme.border

        Behavior on color { ColorAnimation { duration: 260 } }

        // 鼠标位置 → 视差（只观察，不抢事件）
        HoverHandler {
            id: parallaxTrack
            onPointChanged: {
                root.parX = (point.position.x / Math.max(1, shell.width) - 0.5) * 2;
                root.parY = (point.position.y / Math.max(1, shell.height) - 0.5) * 2;
            }
            onHoveredChanged: {
                if (!hovered) {
                    root.parX = 0;
                    root.parY = 0;
                }
            }
        }

        // ---------------------------------------------------------- 背景氛围
        Item {
            id: backdrop
            anchors.fill: parent
            clip: true

            FloatLayer {
                anchors.fill: parent
                particleColor: theme.accent
                count: 22
                opacity: 0.85
            }

            Glow {
                id: glowA
                glowColor: theme.glow1
                diameter: 760
                intensity: 0.62
                driftY: -260
                parallaxX: root.parX * -26
                parallaxY: root.parY * -18

                SequentialAnimation on breath {
                    loops: Animation.Infinite
                    NumberAnimation { from: 0.96; to: 1.06; duration: 6200; easing.type: Easing.InOutSine }
                    NumberAnimation { from: 1.06; to: 0.96; duration: 6200; easing.type: Easing.InOutSine }
                }
                SequentialAnimation on driftX {
                    loops: Animation.Infinite
                    NumberAnimation { from: -220; to: -150; duration: 9000; easing.type: Easing.InOutSine }
                    NumberAnimation { from: -150; to: -220; duration: 9000; easing.type: Easing.InOutSine }
                }
            }

            Glow {
                glowColor: theme.glow2
                diameter: 680
                intensity: 0.52
                driftX: backdrop.width - 680 + 240
                driftY: backdrop.height - 680 + 260
                parallaxX: root.parX * 22
                parallaxY: root.parY * 16

                SequentialAnimation on breath {
                    loops: Animation.Infinite
                    NumberAnimation { from: 1.04; to: 0.94; duration: 7400; easing.type: Easing.InOutSine }
                    NumberAnimation { from: 0.94; to: 1.04; duration: 7400; easing.type: Easing.InOutSine }
                }
            }
        }

        // ------------------------------------------------------------- 布局
        RowLayout {
            anchors.fill: parent
            spacing: 0

            // ===================================================== 侧边栏
            Rectangle {
                Layout.preferredWidth: 216
                Layout.fillHeight: true
                color: Qt.rgba(theme.surface.r, theme.surface.g, theme.surface.b, theme.dark ? 0.55 : 0.72)

                Behavior on color { ColorAnimation { duration: 260 } }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.topMargin: 22
                    anchors.bottomMargin: 16
                    spacing: 0

                    // Logo
                    Item {
                        Layout.preferredHeight: 62
                        Layout.leftMargin: 22
                        Layout.rightMargin: 18
                        Layout.fillWidth: true

                        Item {
                            id: mark
                            width: 38
                            height: 38
                            anchors.verticalCenter: parent.verticalCenter

                            Rectangle {
                                anchors.fill: parent
                                radius: width / 2
                                color: theme.accentSoft
                                Behavior on color { ColorAnimation { duration: 260 } }
                            }
                            // 两片叶子
                            Rectangle {
                                width: 9
                                height: 15
                                radius: 5
                                color: theme.accent
                                x: 10
                                y: 10
                                rotation: -32
                                transformOrigin: Item.Bottom
                                Behavior on color { ColorAnimation { duration: 260 } }
                                SequentialAnimation on rotation {
                                    loops: Animation.Infinite
                                    NumberAnimation { from: -32; to: -22; duration: 2600; easing.type: Easing.InOutSine }
                                    NumberAnimation { from: -22; to: -32; duration: 2600; easing.type: Easing.InOutSine }
                                }
                            }
                            Rectangle {
                                width: 9
                                height: 15
                                radius: 5
                                color: theme.accent
                                x: 20
                                y: 12
                                rotation: 26
                                transformOrigin: Item.Bottom
                                opacity: 0.82
                                Behavior on color { ColorAnimation { duration: 260 } }
                                SequentialAnimation on rotation {
                                    loops: Animation.Infinite
                                    NumberAnimation { from: 26; to: 16; duration: 2800; easing.type: Easing.InOutSine }
                                    NumberAnimation { from: 16; to: 26; duration: 2800; easing.type: Easing.InOutSine }
                                }
                            }
                        }

                        Column {
                            anchors.left: mark.right
                            anchors.leftMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 2

                            Text {
                                text: "Sprout"
                                font.pixelSize: 17
                                font.weight: Font.DemiBold
                                color: theme.text1
                            }
                            Text {
                                text: "新芽启动器"
                                font.pixelSize: 11
                                color: theme.text3
                            }
                        }
                    }

                    // 导航
                    Item {
                        id: navBox
                        Layout.fillWidth: true
                        Layout.topMargin: 18
                        Layout.preferredHeight: navInner.implicitHeight

                        // 选中高亮：整块随页面弹性滑动，比逐项淡入更有连续感
                        Rectangle {
                            id: navPill
                            x: 10
                            width: Math.max(0, navBox.width - 20)
                            height: 46
                            radius: 12
                            color: theme.accentSoft
                            y: root.navIndex * 50

                            Behavior on y {
                                SpringAnimation { spring: 4.2; damping: 0.42; epsilon: 0.001 }
                            }
                            Behavior on color { ColorAnimation { duration: 240 } }
                        }

                        ColumnLayout {
                            id: navInner
                            anchors.fill: parent
                            spacing: 4

                        NavItem {
                            Layout.fillWidth: true
                            icon: "◉\uFE0E"
                            label: "首页"
                            active: root.currentPage === "home"
                            onActivated: root.navigate("home")
                        }
                        NavItem {
                            Layout.fillWidth: true
                            icon: "▦\uFE0E"
                            label: "版本库"
                            active: root.currentPage === "versions"
                            onActivated: root.navigate("versions")
                        }
                        NavItem {
                            Layout.fillWidth: true
                            icon: "◈\uFE0E"
                            label: "模组"
                            active: root.currentPage === "mods"
                            onActivated: root.navigate("mods")
                        }
                        NavItem {
                            Layout.fillWidth: true
                            icon: "☺\uFE0E"
                            label: "账号管理"
                            active: root.currentPage === "accounts"
                            onActivated: root.navigate("accounts")
                        }
                        NavItem {
                            Layout.fillWidth: true
                            icon: "⇄\uFE0E"
                            label: "多人联机"
                            active: root.currentPage === "multiplayer"
                            onActivated: root.navigate("multiplayer")
                        }
                        NavItem {
                            Layout.fillWidth: true
                            icon: "✚\uFE0E"
                            label: "自检诊断"
                            active: root.currentPage === "diagnose"
                            onActivated: root.navigate("diagnose")
                        }
                        NavItem {
                            Layout.fillWidth: true
                            icon: "≡\uFE0E"
                            label: "运行日志"
                            active: root.currentPage === "console"
                            onActivated: root.navigate("console")
                        }
                        NavItem {
                            Layout.fillWidth: true
                            icon: "⚙\uFE0E"
                            label: "设置"
                            active: root.currentPage === "settings"
                            onActivated: root.navigate("settings")
                        }
                        NavItem {
                            Layout.fillWidth: true
                            icon: "ℹ\uFE0E"
                            label: "关于与更新"
                            active: root.currentPage === "about"
                            onActivated: root.navigate("about")
                        }
                        }
                    }

                    Item { Layout.fillHeight: true }

                    // 底部状态
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: 26
                        Layout.rightMargin: 20
                        spacing: 10

                        RowLayout {
                            spacing: 8
                            Rectangle {
                                width: 7
                                height: 7
                                radius: 4
                                color: bridge.javaList.length > 0 ? theme.accent : theme.text3
                                SequentialAnimation on opacity {
                                    loops: Animation.Infinite
                                    NumberAnimation { from: 1.0; to: 0.35; duration: 1600; easing.type: Easing.InOutSine }
                                    NumberAnimation { from: 0.35; to: 1.0; duration: 1600; easing.type: Easing.InOutSine }
                                }
                            }
                            Text {
                                text: bridge.javaList.length > 0
                                      ? ("Java × " + bridge.javaList.length)
                                      : "未检测到 Java"
                                font.pixelSize: 11
                                color: theme.text3
                            }
                            Item { Layout.fillWidth: true }
                        }

                        // 主题快捷切换
                        Row {
                            spacing: 6
                            Repeater {
                                model: theme.available
                                Rectangle {
                                    required property var modelData
                                    width: 16
                                    height: 16
                                    radius: 8
                                    color: modelData.accent
                                    border.width: theme.name === modelData.id ? 2 : 0
                                    border.color: theme.text1
                                    scale: dotMouse.containsMouse ? 1.18 : 1.0
                                    Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                                    MouseArea {
                                        id: dotMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: bridge.setTheme(modelData.id)
                                    }
                                }
                            }
                            Item { Layout.fillWidth: true }
                        }
                    }
                }
            }

            // ===================================================== 主区域
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "transparent"

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    // 顶栏
                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 56

                        Row {
                            anchors.left: parent.left
                            anchors.leftMargin: 26
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 12

                            Text {
                                id: pageTitle
                                text: root.pageTitles[root.currentPage] || ""
                                font.pixelSize: 15
                                font.weight: Font.DemiBold
                                color: theme.text1
                                anchors.verticalCenter: parent.verticalCenter

                                Behavior on opacity {
                                    NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
                                }
                            }

                            Rectangle {
                                width: 1
                                height: 12
                                color: theme.border
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: bridge.busy ? bridge.statusText : "就绪"
                                font.pixelSize: 12
                                color: theme.text3
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            anchors.rightMargin: 132
                            onPressed: root.startSystemMove()
                            onDoubleClicked: root.visibility === Window.Maximized
                                                 ? root.showNormal() : root.showMaximized()
                        }

                        Row {
                            anchors.right: parent.right
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 4

                            Repeater {
                                model: [
                                    { glyph: "—", act: "min" },
                                    { glyph: "▢", act: "max" },
                                    { glyph: "✕", act: "close" }
                                ]
                                Rectangle {
                                    required property var modelData
                                    width: 34
                                    height: 30
                                    radius: 8
                                    color: actMouse.containsMouse
                                           ? (modelData.act === "close"
                                              ? Qt.rgba(0.9, 0.32, 0.32, theme.dark ? 0.28 : 0.16)
                                              : theme.surfaceAlt)
                                           : "transparent"
                                    Behavior on color { ColorAnimation { duration: 140 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.glyph
                                        font.pixelSize: modelData.act === "close" ? 13 : 14
                                        color: modelData.act === "close" && actMouse.containsMouse
                                               ? "#E05555" : theme.text2
                                    }

                                    MouseArea {
                                        id: actMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (modelData.act === "min")
                                                root.showMinimized();
                                            else if (modelData.act === "max")
                                                root.visibility === Window.Maximized ? root.showNormal() : root.showMaximized();
                                            else
                                                Qt.quit();
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // 页面
                    StackView {
                        id: stack
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        initialItem: homeComp
                        clip: true

                        replaceEnter: Transition {
                            ParallelAnimation {
                                NumberAnimation {
                                    property: "opacity"; from: 0.0; to: 1.0
                                    duration: 260; easing.type: Easing.OutCubic
                                }
                                NumberAnimation {
                                    property: "y"; from: 18; to: 0
                                    duration: 340; easing.type: Easing.OutQuint
                                }
                                NumberAnimation {
                                    property: "scale"; from: 0.988; to: 1.0
                                    duration: 340; easing.type: Easing.OutQuint
                                }
                            }
                        }
                        replaceExit: Transition {
                            ParallelAnimation {
                                NumberAnimation {
                                    property: "opacity"; from: 1.0; to: 0.0
                                    duration: 150; easing.type: Easing.InCubic
                                }
                                NumberAnimation {
                                    property: "y"; from: 0; to: -10
                                    duration: 170; easing.type: Easing.InCubic
                                }
                            }
                        }
                    }

                    // 底部进度 / 状态
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: bridge.busy ? 34 : 28
                        color: Qt.rgba(theme.surface.r, theme.surface.g, theme.surface.b, 0.6)

                        Behavior on Layout.preferredHeight {
                            NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
                        }

                        Rectangle {
                            id: progressTrack
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 3
                            color: theme.surfaceAlt
                            visible: bridge.busy

                            Rectangle {
                                id: fillBar
                                height: parent.height
                                radius: 2
                                color: theme.accent
                                clip: true
                                width: parent.width * Math.max(0.02, Math.min(1.0, bridge.progress))

                                Behavior on width {
                                    NumberAnimation { duration: 260; easing.type: Easing.OutCubic }
                                }

                                // 高光扫过：让"正在下载"在视觉上真的在动
                                property real shimmer: 0
                                Rectangle {
                                    width: 70
                                    height: fillBar.height
                                    radius: 2
                                    color: "#FFFFFF"
                                    opacity: 0.32
                                    x: -70 + (fillBar.width + 140) * fillBar.shimmer
                                }

                                NumberAnimation on shimmer {
                                    from: 0; to: 1
                                    duration: 1500
                                    loops: Animation.Infinite
                                    easing.type: Easing.Linear
                                }
                            }
                        }

                        Row {
                            anchors.left: parent.left
                            anchors.leftMargin: 26
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 10

                            Text {
                                text: bridge.statusText
                                font.pixelSize: 11
                                color: theme.text3
                                elide: Text.ElideRight
                                width: Math.min(implicitWidth, 520)
                            }

                            Text {
                                visible: bridge.busy && bridge.downloadSpeedValue > 0
                                text: bridge.downloadSpeed
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                color: theme.accent
                            }
                        }

                        Text {
                            anchors.right: parent.right
                            anchors.rightMargin: 26
                            anchors.verticalCenter: parent.verticalCenter
                            visible: bridge.busy
                            text: Math.round(bridge.progress * 100) + "%"
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                            color: theme.accent
                        }
                    }
                }
            }
        }
    }

    // --------------------------------------------- 整合包拖放到任意界面直接导入
    DropArea {
        id: globalDrop
        objectName: "globalDrop"
        anchors.fill: parent
        onEntered: function (drag) {
            drag.acceptProposedAction();
            dropMask.visible = true;
        }
        onExited: dropMask.visible = false
        onDropped: function (drop) {
            dropMask.visible = false;
            bridge.dropModpacks(drop.urls);
            drop.acceptProposedAction();
        }
    }

    Rectangle {
        id: dropMask
        objectName: "dropMask"
        anchors.fill: parent
        visible: false
        color: Qt.rgba(0, 0, 0, 0.45)
        z: 900

        Rectangle {
            anchors.centerIn: parent
            width: 420
            height: 140
            radius: 16
            color: theme.card
            border.width: 2
            border.color: theme.accent

            Column {
                anchors.centerIn: parent
                spacing: 8

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "松开鼠标开始导入"
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    color: theme.text1
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "支持整合包 (*.mrpack / *.zip / *.cf)，将自动下载并导入到新实例"
                    font.pixelSize: 11
                    color: theme.text3
                }
            }
        }
    }

    // ------------------------------------------------------------- 提示浮层
    UpdateDialog {
        anchors.fill: parent
    }

    Toast {
        id: toastLayer
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: 26
        anchors.bottomMargin: 52
    }

    Connections {
        target: bridge
        function onToast(text, level) {
            toastLayer.show(text, level);
        }
    }
}
