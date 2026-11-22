import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: page

    property var dirs: []

    Component.onCompleted: page.dirs = bridge.candidateDirs()

    Flickable {
        id: flick
        anchors.fill: parent
        anchors.leftMargin: 26
        anchors.rightMargin: 22
        anchors.topMargin: 4
        anchors.bottomMargin: 4
        contentWidth: width
        contentHeight: col.implicitHeight + 20
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        ColumnLayout {
            id: col
            width: flick.width
            spacing: 14

            // ------------------------------------------------------- 外观
            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: 148
                corner: 14
                interactive: false

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 12

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "外观主题"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: theme.text1
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: "当前：" + theme.label
                            font.pixelSize: 11
                            color: theme.text3
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12

                        Repeater {
                            model: theme.available

                            Rectangle {
                                required property var modelData
                                Layout.preferredWidth: 96
                                Layout.preferredHeight: 68
                                radius: 12
                                color: theme.surfaceAlt
                                border.width: theme.name === modelData.id ? 2 : 1
                                border.color: theme.name === modelData.id ? theme.accent : theme.border
                                scale: themeMouse.containsMouse ? 1.03 : 1.0
                                Behavior on scale { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }
                                Behavior on border.color { ColorAnimation { duration: 180 } }

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.leftMargin: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 22
                                    height: 22
                                    radius: 11
                                    color: modelData.accent
                                }

                                Text {
                                    anchors.left: parent.left
                                    anchors.leftMargin: 44
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.label
                                    font.pixelSize: 12
                                    color: theme.text2
                                }

                                MouseArea {
                                    id: themeMouse
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

            // --------------------------------------------------- 下载与镜像
            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: 148
                corner: 14
                interactive: false

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 12

                    Text {
                        text: "下载源"
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                        color: theme.text1
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Repeater {
                            model: [
                                { key: "auto", label: "智能", hint: "镜像优先，失败回退官方" },
                                { key: "bmclapi", label: "BMCLAPI", hint: "国内镜像，速度稳定" },
                                { key: "fastmc", label: "FastMC", hint: "备用国内镜像" },
                                { key: "official", label: "官方", hint: "直连 Mojang" }
                            ]

                            Rectangle {
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredHeight: 60
                                radius: 12
                                color: bridge.mirror === modelData.key ? theme.accentSoft : theme.surfaceAlt
                                border.width: 1
                                border.color: bridge.mirror === modelData.key ? theme.accent : "transparent"
                                Behavior on color { ColorAnimation { duration: 180 } }

                                Column {
                                    anchors.centerIn: parent
                                    spacing: 4

                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: modelData.label
                                        font.pixelSize: 13
                                        font.weight: bridge.mirror === modelData.key ? Font.DemiBold : Font.Normal
                                        color: bridge.mirror === modelData.key ? theme.accent : theme.text1
                                    }
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: modelData.hint
                                        font.pixelSize: 10
                                        color: theme.text3
                                    }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: bridge.setMirror(modelData.key)
                                }
                            }
                        }
                    }
                }
            }

            // ------------------------------------------------------- 内存
            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: 118
                corner: 14
                interactive: false

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "最大内存"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: theme.text1
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: bridge.memoryMb + " MB"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: theme.accent
                        }
                    }

                    Slider {
                        id: memSlider
                        Layout.fillWidth: true
                        from: 1024
                        to: 16384
                        stepSize: 512
                        value: bridge.memoryMb
                        onMoved: bridge.setMemory(Math.round(value))

                        background: Rectangle {
                            x: memSlider.leftPadding
                            y: memSlider.topPadding + memSlider.availableHeight / 2 - 3
                            width: memSlider.availableWidth
                            height: 6
                            radius: 3
                            color: theme.surfaceAlt

                            Rectangle {
                                width: memSlider.visualPosition * parent.width
                                height: parent.height
                                radius: 3
                                color: theme.accent
                                Behavior on width { NumberAnimation { duration: 90 } }
                            }
                        }

                        handle: Rectangle {
                            x: memSlider.leftPadding + memSlider.visualPosition * (memSlider.availableWidth - width)
                            y: memSlider.topPadding + memSlider.availableHeight / 2 - height / 2
                            width: 18
                            height: 18
                            radius: 9
                            color: theme.surface
                            border.width: 3
                            border.color: theme.accent
                            scale: memSlider.pressed ? 1.15 : 1.0
                            Behavior on scale { NumberAnimation { duration: 120 } }
                        }
                    }

                    Text {
                        text: "建议 4096 MB 起步，模组整合包可提高到 6144 - 8192 MB"
                        font.pixelSize: 11
                        color: theme.text3
                    }
                }
            }

            // ------------------------------------------ 模组来源与下载内核
            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: 246
                corner: 14
                interactive: false

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "模组来源"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: theme.text1
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: bridge.modSource === "curseforge" ? "CurseForge" : "Modrinth"
                            font.pixelSize: 11
                            color: theme.accent
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Repeater {
                            model: [
                                { key: "modrinth", label: "Modrinth", hint: "开放接口，无需密钥" },
                                { key: "curseforge", label: "CurseForge", hint: "需要配置 API Key" }
                            ]

                            Rectangle {
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredHeight: 54
                                radius: 12
                                color: bridge.modSource === modelData.key ? theme.accentSoft : theme.surfaceAlt
                                border.width: 1
                                border.color: bridge.modSource === modelData.key ? theme.accent : "transparent"
                                Behavior on color { ColorAnimation { duration: 180 } }

                                Column {
                                    anchors.centerIn: parent
                                    spacing: 3

                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: modelData.label
                                        font.pixelSize: 12
                                        font.weight: bridge.modSource === modelData.key ? Font.DemiBold : Font.Normal
                                        color: bridge.modSource === modelData.key ? theme.accent : theme.text1
                                    }
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: modelData.hint
                                        font.pixelSize: 10
                                        color: theme.text3
                                    }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: bridge.setModSource(modelData.key)
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 36
                        radius: 10
                        color: theme.surfaceAlt
                        border.width: 1
                        border.color: cfField.activeFocus ? theme.accent : "transparent"
                        Behavior on border.color { ColorAnimation { duration: 160 } }

                        TextField {
                            id: cfField
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            background: Item {}
                            placeholderText: "CurseForge API Key（留空则仅可用 Modrinth）"
                            placeholderTextColor: theme.text3
                            color: theme.text1
                            font.pixelSize: 12
                            echoMode: TextInput.PasswordEchoOnEdit
                            verticalAlignment: TextInput.AlignVCenter
                            text: bridge.cfApiKey
                            onEditingFinished: bridge.setCfApiKey(text)
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12

                        Text {
                            text: "下载并发线程"
                            font.pixelSize: 12
                            color: theme.text2
                        }
                        Slider {
                            id: concSlider
                            Layout.fillWidth: true
                            from: 10
                            to: 64
                            stepSize: 2
                            value: bridge.concurrency
                            onMoved: bridge.setConcurrency(Math.round(value))

                            background: Rectangle {
                                x: concSlider.leftPadding
                                y: concSlider.topPadding + concSlider.availableHeight / 2 - 3
                                width: concSlider.availableWidth
                                height: 6
                                radius: 3
                                color: theme.surfaceAlt

                                Rectangle {
                                    width: concSlider.visualPosition * parent.width
                                    height: parent.height
                                    radius: 3
                                    color: theme.accent
                                    Behavior on width { NumberAnimation { duration: 90 } }
                                }
                            }

                            handle: Rectangle {
                                x: concSlider.leftPadding + concSlider.visualPosition * (concSlider.availableWidth - width)
                                y: concSlider.topPadding + concSlider.availableHeight / 2 - height / 2
                                width: 16
                                height: 16
                                radius: 8
                                color: theme.surface
                                border.width: 3
                                border.color: theme.accent
                            }
                        }
                        Text {
                            text: bridge.concurrency + " 线程"
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            color: theme.accent
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "范围 10 - 64 线程，默认 16；线程越多占用带宽越高，下载界面会实时显示速度"
                        font.pixelSize: 11
                        color: theme.text3
                        wrapMode: Text.WordWrap
                    }
                }
            }

            // --------------------------------------------------- 游戏目录
            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.max(150, 96 + Math.min(page.dirs.length, 4) * 40)
                corner: 14
                interactive: false

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "游戏目录"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: theme.text1
                        }
                        Item { Layout.fillWidth: true }
                        SproutButton {
                            text: "打开"
                            primary: false
                            implicitHeight: 28
                            fontSize: 11
                            onClicked: bridge.openPath(bridge.mcDir)
                        }
                        SproutButton {
                            text: "重新检测"
                            primary: false
                            implicitHeight: 28
                            fontSize: 11
                            onClicked: page.dirs = bridge.candidateDirs()
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: bridge.mcDir
                        font.pixelSize: 11
                        color: theme.text3
                        elide: Text.ElideMiddle
                    }

                    Repeater {
                        model: page.dirs

                        Rectangle {
                            required property var modelData
                            visible: modelData.current || modelData.score > 0
                            Layout.fillWidth: true
                            Layout.preferredHeight: 36
                            radius: 9
                            color: modelData.current ? theme.accentSoft : (dirMouse.containsMouse ? theme.surfaceAlt : "transparent")
                            Behavior on color { ColorAnimation { duration: 150 } }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                spacing: 10

                                Text {
                                    Layout.fillWidth: true
                                    text: modelData.path
                                    font.pixelSize: 12
                                    color: modelData.current ? theme.accent : theme.text2
                                    elide: Text.ElideMiddle
                                }
                                Text {
                                    text: modelData.current ? "使用中" : ("评分 " + modelData.score)
                                    font.pixelSize: 11
                                    color: theme.text3
                                }
                            }

                            MouseArea {
                                id: dirMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                enabled: !modelData.current
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    bridge.setMcDir(modelData.path);
                                    page.dirs = bridge.candidateDirs();
                                }
                            }
                        }
                    }
                }
            }

            // ------------------------------------------------ 更多游戏目录
            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: 128 + Math.min(bridge.gameRoots.length, 5) * 38
                corner: 14
                interactive: false

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            text: "多目录扫描"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: theme.text1
                        }

                        Text {
                            text: "共 " + bridge.gameRoots.length + " 个目录"
                            font.pixelSize: 11
                            color: theme.text3
                        }

                        Item { Layout.fillWidth: true }

                        SproutButton {
                            text: "添加目录"
                            primary: false
                            implicitHeight: 30
                            fontSize: 12
                            onClicked: bridge.browseGameDir()
                        }

                        SproutButton {
                            text: "自动检测"
                            primary: false
                            implicitHeight: 30
                            fontSize: 12
                            onClicked: bridge.autoDetectGameDirs()
                        }
                    }

                    Repeater {
                        model: bridge.gameRoots

                        Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 32
                            radius: 9
                            color: modelData.exists ? theme.surfaceAlt : "transparent"

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 8
                                spacing: 10

                                Text {
                                    Layout.fillWidth: true
                                    text: modelData.path
                                    font.pixelSize: 12
                                    color: modelData.exists ? theme.text2 : theme.text3
                                    elide: Text.ElideMiddle
                                }

                                Text {
                                    text: modelData.exists ? (modelData.versions + " 个版本") : "目录不存在"
                                    font.pixelSize: 11
                                    color: theme.text3
                                }

                                Text {
                                    visible: modelData.current
                                    text: "主力"
                                    font.pixelSize: 11
                                    color: theme.accent
                                }

                                Text {
                                    visible: modelData.manual
                                    text: "手动"
                                    font.pixelSize: 11
                                    color: theme.accentSoft
                                }

                                SproutButton {
                                    visible: modelData.manual
                                    text: "移除"
                                    primary: false
                                    implicitHeight: 24
                                    implicitWidth: 52
                                    fontSize: 11
                                    onClicked: bridge.removeGameDir(modelData.path)
                                }
                            }
                        }
                    }
                }
            }

            // ------------------------------------------------------ Java
            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: 150 + Math.min(bridge.javaList.length, 3) * 40
                corner: 14
                interactive: false

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "Java 运行时"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: theme.text1
                        }
                        Item { Layout.fillWidth: true }
                        SproutButton {
                            text: "检测"
                            primary: false
                            implicitHeight: 28
                            fontSize: 11
                            onClicked: bridge.detectJava()
                        }
                        SproutButton {
                            text: "获取 8"
                            primary: false
                            implicitHeight: 28
                            fontSize: 11
                            active: !bridge.busy
                            onClicked: bridge.downloadJava(8)
                        }
                        SproutButton {
                            text: "获取 17"
                            primary: false
                            implicitHeight: 28
                            fontSize: 11
                            active: !bridge.busy
                            onClicked: bridge.downloadJava(17)
                        }
                        SproutButton {
                            text: "获取 21"
                            primary: false
                            implicitHeight: 28
                            fontSize: 11
                            active: !bridge.busy
                            onClicked: bridge.downloadJava(21)
                        }
                    }

                    Text {
                        text: bridge.javaList.length > 0
                              ? ("已找到 " + bridge.javaList.length + " 个运行时，启动时按版本自动匹配")
                              : "未找到可用 Java，点击上方按钮自动获取"
                        font.pixelSize: 11
                        color: theme.text3
                    }

                    Repeater {
                        model: bridge.javaList

                        Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 36
                            radius: 9
                            color: theme.surfaceAlt

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                spacing: 10

                                Rectangle {
                                    width: 26
                                    height: 20
                                    radius: 6
                                    color: theme.accentSoft
                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.major
                                        font.pixelSize: 10
                                        font.weight: Font.DemiBold
                                        color: theme.accent
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: modelData.path
                                    font.pixelSize: 11
                                    color: theme.text2
                                    elide: Text.ElideMiddle
                                }

                                Text {
                                    text: (modelData.vendor || "") + " " + (modelData.arch || "")
                                    font.pixelSize: 10
                                    color: theme.text3
                                }
                            }
                        }
                    }
                }
            }

            // --------------------------------------------------- 工具箱
            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: 316
                corner: 14
                interactive: false

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "工具箱"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: theme.text1
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: "内存清理与线路加速"
                            font.pixelSize: 10
                            color: theme.text3
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: "优化内存"
                                font.pixelSize: 12
                                color: theme.text1
                            }
                            Text {
                                text: bridge.memorySummary
                                font.pixelSize: 10
                                color: theme.text3
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }

                        SproutButton {
                            text: bridge.memBusy ? "优化中…" : "立即优化"
                            primary: false
                            active: !bridge.memBusy
                            implicitHeight: 30
                            fontSize: 11
                            onClicked: bridge.optimizeMemory()
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 1
                        color: theme.border
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: "GitHub 加速"
                                font.pixelSize: 12
                                color: theme.text1
                            }
                            Text {
                                text: bridge.githubAccel
                                      ? ("已开启 · " + bridge.githubMirrorId)
                                      : "关闭后所有 GitHub 下载走直连"
                                font.pixelSize: 10
                                color: theme.text3
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }

                        SproutButton {
                            text: bridge.githubAccel ? "已开启" : "已关闭"
                            primary: bridge.githubAccel
                            implicitHeight: 30
                            fontSize: 11
                            onClicked: bridge.setGithub(!bridge.githubAccel, bridge.githubMirrorId)
                        }
                    }

                    Row {
                        Layout.fillWidth: true
                        spacing: 8

                        Repeater {
                            model: bridge.githubMirrorOptions()

                            SproutButton {
                                required property var modelData
                                text: modelData.name
                                primary: bridge.githubMirrorId === modelData.id
                                implicitHeight: 26
                                fontSize: 10
                                onClicked: bridge.setGithub(true, modelData.id)
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 1
                        color: theme.border
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: "Steam 区服加速"
                                font.pixelSize: 12
                                color: theme.text1
                            }
                            Text {
                                text: bridge.steamRoute
                                font.pixelSize: 10
                                color: theme.text3
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Text {
                                objectName: "steamClientCell"
                                text: bridge.steamClientCell
                                font.pixelSize: 10
                                color: theme.text3
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }

                        SproutButton {
                            objectName: "steamApplyCell"
                            text: "应用到 Steam"
                            primary: false
                            implicitHeight: 30
                            fontSize: 11
                            onClicked: bridge.applySteamCell()
                        }

                        SproutButton {
                            objectName: "steamProbe"
                            text: "重新探测"
                            primary: false
                            implicitHeight: 30
                            fontSize: 11
                            onClicked: bridge.refreshAccel()
                        }

                        SproutButton {
                            text: bridge.steamAccel ? "已开启" : "已关闭"
                            primary: bridge.steamAccel
                            implicitHeight: 30
                            fontSize: 11
                            onClicked: bridge.setSteam(!bridge.steamAccel, bridge.steamRegionId)
                        }
                    }

                    Row {
                        Layout.fillWidth: true
                        spacing: 8

                        Repeater {
                            model: bridge.steamRegionOptions()

                            SproutButton {
                                required property var modelData
                                text: modelData.name
                                primary: bridge.steamRegionId === modelData.id
                                implicitHeight: 26
                                fontSize: 10
                                onClicked: bridge.setSteam(true, modelData.id)
                            }
                        }
                    }
                }
            }

            Item { Layout.preferredHeight: 4 }
        }
    }
}
