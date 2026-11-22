import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: page

    readonly property var feat: bridge.featured || ({})
    readonly property string featId: feat.id !== undefined ? feat.id : ""
    readonly property bool featInstalled: feat.installed === true

    signal requestPage(string name, string arg)

    function chosenId() {
        var want = bridge.launchChoice;
        if (want && want.length > 0)
            return want;
        // 未显式选择时，默认指向本机已安装的第一个版本，避免显示「推荐启动」
        var list = bridge.installedList || [];
        if (list.length > 0)
            return list[0].id;
        return page.featId;
    }

    function chosenName() {
        var want = page.chosenId();
        var list = bridge.installedList || [];
        for (var i = 0; i < list.length; ++i) {
            if (list[i].id === want)
                return list[i].name;
        }
        return want;
    }

    function chosenInstalled() {
        var want = page.chosenId();
        var list = bridge.installedList || [];
        for (var i = 0; i < list.length; ++i) {
            if (list[i].id === want)
                return true;
        }
        return page.featInstalled;
    }

    Flickable {
        id: flick
        anchors.fill: parent
        anchors.leftMargin: 26
        anchors.rightMargin: 22
        anchors.topMargin: 4
        anchors.bottomMargin: 4
        contentWidth: width
        contentHeight: col.implicitHeight + 16
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        ColumnLayout {
            id: col
            width: flick.width
            spacing: 16

            // ---------------------------------------------------- 推荐启动
            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: 232
                corner: 16
                interactive: false

                Item {
                    anchors.fill: parent
                    anchors.margins: 26

                    Column {
                        width: Math.max(240, parent.width - 300)
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 10

                        Row {
                            spacing: 8
                            Text {
                                text: "推荐启动"
                                font.pixelSize: 11
                                font.letterSpacing: 2
                                color: theme.text3
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Rectangle {
                                width: 6
                                height: 6
                                radius: 3
                                color: bridge.running ? "#E5A94D" : theme.accent
                                anchors.verticalCenter: parent.verticalCenter
                                SequentialAnimation on opacity {
                                    loops: Animation.Infinite
                                    NumberAnimation { from: 1.0; to: 0.3; duration: 1500; easing.type: Easing.InOutSine }
                                    NumberAnimation { from: 0.3; to: 1.0; duration: 1500; easing.type: Easing.InOutSine }
                                }
                            }
                        }

                        // 当前要启动的游戏名：直接显示在左侧空白处、「推荐启动」下方
                        Text {
                            id: bigName
                            width: parent.width
                            text: page.chosenId() ? page.chosenName() : "暂无版本"
                            // 名字越长字号越小，避免溢出右侧
                            font.pixelSize: text.length > 16 ? 26 : (text.length > 10 ? 32 : 42)
                            font.weight: Font.DemiBold
                            color: theme.text1
                            elide: Text.ElideRight
                            opacity: 0
                            Component.onCompleted: introA.start()
                            NumberAnimation {
                                id: introA
                                target: bigName
                                property: "opacity"
                                to: 1
                                duration: 460
                                easing.type: Easing.OutCubic
                            }
                        }

                        Row {
                            spacing: 8

                            Rectangle {
                                visible: page.chosenId() !== ""
                                width: kindLabel.implicitWidth + 16
                                height: 22
                                radius: 11
                                color: theme.accentSoft
                                Text {
                                    id: kindLabel
                                    anchors.centerIn: parent
                                    text: page.chosenInstalled() ? "已安装" : "需下载"
                                    font.pixelSize: 11
                                    color: theme.accent
                                }
                            }

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.max(0, parent.width - 80)
                                text: page.chosenId()
                                elide: Text.ElideRight
                                font.pixelSize: 12
                                color: theme.text3
                            }
                        }
                    }

                    Column {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 10
                        width: 400

                        Row {
                            anchors.right: parent.right
                            spacing: 8

                            SproutButton {
                                id: launchButton
                                // 运行中悬停显示「结束游戏」，点击直接结束游戏进程
                                text: bridge.running ? (launchButton.hovered ? "结束游戏" : "游戏运行中")
                                                     : (page.chosenInstalled() ? "启动游戏" : "安装并启动")
                                active: bridge.running || (page.chosenId() !== "" && !bridge.busy)
                                implicitHeight: 48
                                fontSize: 15
                                onClicked: {
                                    if (bridge.running) {
                                        bridge.killGame();
                                        return;
                                    }
                                    bridge.launchChosen();
                                }
                            }

                            SproutButton {
                                text: "▾"
                                primary: false
                                implicitHeight: 48
                                implicitWidth: 42
                                fontSize: 14
                                active: (bridge.installedList || []).length > 0 && !bridge.running
                                onClicked: launchPicker.open()
                            }
                        }

                        Text {
                            anchors.right: parent.right
                            text: "内存 " + bridge.memoryMb + " MB · " + bridge.mirror
                            font.pixelSize: 11
                            color: theme.text3
                        }
                    }
                }
            }

            // ------------------------------------------------------ 统计
            RowLayout {
                Layout.fillWidth: true
                spacing: 14

                Repeater {
                    model: [
                        { label: "版本总数", value: bridge.versionCount, hint: "来自官方清单" },
                        { label: "已安装", value: bridge.installedCount, hint: "可直接启动" },
                        { label: "Java 运行时", value: bridge.javaList.length, hint: "自动匹配版本" }
                    ]

                    Card {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: 92
                        corner: 14

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            enabled: modelData.label === "已装" || modelData.label === "已安装"
                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: {
                                installedPopup.view = "list";
                                installedPopup.open();
                            }
                        }

                        Column {
                            anchors.left: parent.left
                            anchors.leftMargin: 20
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 4

                            Text {
                                text: modelData.label
                                font.pixelSize: 12
                                color: theme.text3
                            }
                            Text {
                                text: modelData.value
                                font.pixelSize: 24
                                font.weight: Font.DemiBold
                                color: theme.text1
                            }
                            Text {
                                text: modelData.hint
                                font.pixelSize: 11
                                color: theme.text3
                            }
                        }
                    }
                }
            }

            // -------------------------------------------------- 版本速览
            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: 268
                corner: 14
                interactive: false

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "版本速览"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: theme.text1
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: "最近 12 个"
                            font.pixelSize: 11
                            color: theme.text3
                        }
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 2
                        model: bridge.versionsModel
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        delegate: Rectangle {
                            id: rowItem
                            required property int index
                            required property string id
                            required property string type
                            required property string releaseTime
                            required property bool installed
                            required property bool isLatest

                            width: ListView.view.width
                            height: index < 12 ? 30 : 0
                            visible: index < 12
                            radius: 8
                            color: rowMouse.containsMouse ? theme.surfaceAlt : "transparent"
                            Behavior on color { ColorAnimation { duration: 140 } }

                            opacity: 0
                            Component.onCompleted: {
                                fadeDelay.interval = Math.min(index * 22, 320);
                                fadeDelay.start();
                            }
                            Timer { id: fadeDelay; onTriggered: fadeIn.start() }
                            NumberAnimation {
                                id: fadeIn
                                target: rowItem
                                property: "opacity"
                                to: 1.0
                                duration: 240
                                easing.type: Easing.OutCubic
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                spacing: 10

                                Rectangle {
                                    width: 6
                                    height: 6
                                    radius: 3
                                    color: rowItem.installed ? theme.accent : theme.text3
                                    opacity: rowItem.installed ? 1.0 : 0.5
                                }
                                Text {
                                    text: rowItem.id
                                    font.pixelSize: 13
                                    color: theme.text1
                                }
                                Rectangle {
                                    visible: rowItem.isLatest
                                    width: 34
                                    height: 16
                                    radius: 8
                                    color: theme.accentSoft
                                    Text {
                                        anchors.centerIn: parent
                                        text: "最新"
                                        font.pixelSize: 10
                                        color: theme.accent
                                    }
                                }
                                Item { Layout.fillWidth: true }
                                Text {
                                    text: rowItem.type === "snapshot" ? "快照" : "正式"
                                    font.pixelSize: 11
                                    color: theme.text3
                                }
                                Text {
                                    text: rowItem.releaseTime
                                    font.pixelSize: 11
                                    color: theme.text3
                                }
                                Text {
                                    text: rowItem.installed ? "已安装" : "未安装"
                                    font.pixelSize: 11
                                    color: rowItem.installed ? theme.accent : theme.text3
                                    Layout.preferredWidth: 40
                                    horizontalAlignment: Text.AlignRight
                                }
                            }

                            MouseArea {
                                id: rowMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: bridge.launchVersion(rowItem.id)
                            }
                        }
                    }
                }
            }

            Item { Layout.preferredHeight: 2 }
        }
    }

    // ================================================================ 启动目标选择
    Popup {
        id: launchPicker
        objectName: "launchPicker"
        parent: Overlay.overlay
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        width: Math.min(520, Math.max(360, (parent ? parent.width : 520) - 80))
        modal: true
        focus: true
        padding: 0
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            radius: 16
            color: theme.card
            border.width: 1
            border.color: theme.border
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 10

            Text {
                text: "选择要启动的游戏"
                font.pixelSize: 13
                font.weight: Font.DemiBold
                color: theme.text1
            }

            ListView {
                id: pickList
                objectName: "pickList"
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(360, Math.max(64, contentHeight + 8))
                clip: true
                spacing: 4
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                model: bridge.installedList

                delegate: Rectangle {
                    id: pickRow
                    required property var modelData
                    width: ListView.view.width
                    height: 56
                    radius: 10
                    color: pickMouse.containsMouse ? theme.surfaceAlt : "transparent"
                    Behavior on color { ColorAnimation { duration: 140 } }

                    Column {
                        anchors.left: parent.left
                        anchors.leftMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        // 宽度写死绑定，不依赖 anchors 推导，确保 elide 一定生效
                        width: Math.max(0, pickRow.width - 24 - 56)
                        spacing: 2
                        Text {
                            width: parent.width
                            text: modelData.name
                            font.pixelSize: 13
                            color: theme.text1
                            elide: Text.ElideRight
                            wrapMode: Text.NoWrap
                        }
                        Text {
                            width: parent.width
                            text: modelData.versionId + (modelData.loader ? (" · " + modelData.loader) : "")
                            font.pixelSize: 11
                            color: theme.text3
                            elide: Text.ElideRight
                            wrapMode: Text.NoWrap
                        }
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        visible: page.chosenId() === modelData.id
                        text: "当前"
                        font.pixelSize: 11
                        color: theme.accent
                    }

                    MouseArea {
                        id: pickMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            bridge.setLaunchChoice(modelData.id);
                            launchPicker.close();
                        }
                    }
                }
            }

            Text {
                visible: pickList.count === 0
                text: "还没有已安装的游戏，先去版本库安装一个吧"
                font.pixelSize: 12
                color: theme.text3
            }
        }
    }

    // ================================================================ 已安装游戏面板
    Popup {
        id: installedPopup
        objectName: "installedPopup"
        parent: Overlay.overlay
        property string view: "list"
        property var current: ({})
        property string filterText: ""
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        width: 700
        height: 660
        modal: true
        focus: true
        padding: 0
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            radius: 16
            color: theme.card
            border.width: 1
            border.color: theme.border
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12

            // ------------------------------------------------ 顶部标题
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Text {
                    text: installedPopup.view === "list" ? "已安装的游戏" : (installedPopup.current.name || "")
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    color: theme.text1
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                Text {
                    text: (bridge.installedList || []).length + " 个可直接启动"
                    font.pixelSize: 11
                    color: theme.text3
                }

                SproutButton {
                    visible: installedPopup.view !== "list"
                    text: "返回列表"
                    primary: false
                    implicitHeight: 30
                    fontSize: 12
                    onClicked: installedPopup.view = "list"
                }

                SproutButton {
                    text: "关闭"
                    primary: false
                    implicitHeight: 30
                    fontSize: 12
                    onClicked: installedPopup.close()
                }
            }

            // ------------------------------------------------ 列表视图
            ListView {
                id: instList
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: installedPopup.view === "list"
                clip: true
                spacing: 6
                model: bridge.installedList

                delegate: Rectangle {
                    id: instRow
                    required property var modelData
                    width: ListView.view.width
                    height: 64
                    radius: 12
                    color: instMouse.containsMouse ? theme.surfaceAlt : theme.surface
                    border.width: 1
                    border.color: instMouse.containsMouse ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.5)
                                                          : theme.border
                    Behavior on color { ColorAnimation { duration: 150 } }
                    Behavior on border.color { ColorAnimation { duration: 150 } }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 14
                        spacing: 12

                        Rectangle {
                            width: 34
                            height: 34
                            radius: 10
                            color: theme.accentSoft
                            Text {
                                anchors.centerIn: parent
                                text: "▶"
                                font.pixelSize: 13
                                color: theme.accent
                            }
                        }

                        Column {
                            Layout.fillWidth: true
                            spacing: 3
                            Text {
                                text: modelData.name
                                font.pixelSize: 13
                                color: theme.text1
                                elide: Text.ElideRight
                                wrapMode: Text.NoWrap
                                width: parent.width
                            }
                            Text {
                                text: modelData.versionId + (modelData.loader ? (" · " + modelData.loader) : "")
                                font.pixelSize: 11
                                color: theme.text3
                                elide: Text.ElideRight
                                wrapMode: Text.NoWrap
                                width: parent.width
                            }
                        }

                        SproutButton {
                            text: "设置"
                            primary: false
                            implicitHeight: 32
                            fontSize: 12
                            onClicked: {
                                installedPopup.current = modelData;
                                installedPopup.view = "settings";
                            }
                        }

                        SproutButton {
                            text: "启动"
                            primary: true
                            active: !bridge.busy && !bridge.running
                            implicitHeight: 32
                            fontSize: 12
                            onClicked: {
                                bridge.setLaunchChoice(modelData.id);
                                bridge.launchChosen();
                                installedPopup.close();
                            }
                        }
                    }

                    MouseArea {
                        id: instMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.NoButton
                    }
                }
            }

            // ------------------------------------------------ 设置视图
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: installedPopup.view === "settings"
                spacing: 12

                onVisibleChanged: {
                    if (visible)
                        bridge.loadInstanceMods(installedPopup.current.id || "");
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 108
                    radius: 12
                    color: theme.surface
                    border.width: 1
                    border.color: theme.border

                    Column {
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 6
                        Text {
                            text: installedPopup.current.name || ""
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                            color: theme.text1
                        }
                        Text {
                            text: "版本 " + (installedPopup.current.versionId || "")
                                  + "  ·  加载器 " + (installedPopup.current.loader || "vanilla")
                            font.pixelSize: 12
                            color: theme.text2
                        }
                        Text {
                            text: installedPopup.current.gameDir || ""
                            font.pixelSize: 11
                            color: theme.text3
                            elide: Text.ElideMiddle
                            width: 600
                        }
                    }
                }

                Text {
                    text: "游戏设置"
                    font.pixelSize: 12
                    color: theme.text3
                }

                SproutButton {
                    objectName: "loadModsBtn"
                    Layout.fillWidth: true
                    text: "装载模组（按该实例的版本与加载器筛选模组市场）"
                    primary: true
                    implicitHeight: 42
                    fontSize: 13
                    onClicked: {
                        // 目标实例与筛选条件由 bridge 统一设置；缺加载器时会弹出加载器选择框
                        bridge.requestModsForInstance(installedPopup.current.id || "");
                        installedPopup.close();
                        page.requestPage("mods", "");
                    }
                }

                SproutButton {
                    Layout.fillWidth: true
                    text: "导出为整合包"
                    primary: false
                    active: !bridge.busy
                    implicitHeight: 42
                    fontSize: 13
                    onClicked: {
                        bridge.useGameForMods(installedPopup.current.id || "");
                        var name = (installedPopup.current.name || "sprout-pack") + ".zip";
                        var p = bridge.pickSaveFile("导出整合包", "压缩包 (*.zip)", name);
                        if (p && p.length > 0)
                            bridge.exportModpack(p);
                    }
                }

                SproutButton {
                    Layout.fillWidth: true
                    text: "打开游戏目录"
                    primary: false
                    implicitHeight: 42
                    fontSize: 13
                    onClicked: bridge.openGameDir(installedPopup.current.id || "")
                }

                // ------------------------------------------ 该实例已安装模组（启用/禁用）
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 150
                    radius: 12
                    color: theme.surface
                    border.width: 1
                    border.color: theme.border
                    clip: true

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Text {
                                text: "已安装模组（" + bridge.instanceModCount + "）"
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                                color: theme.text1
                            }

                            Item { Layout.fillWidth: true }

                            SproutButton {
                                objectName: "instModInstall"
                                text: "安装模组…"
                                primary: true
                                active: !bridge.busy
                                implicitHeight: 30
                                fontSize: 12
                                onClicked: bridge.installModJarToInstance(installedPopup.current.id || "")
                            }

                            SproutButton {
                                text: "刷新"
                                primary: false
                                active: true
                                implicitHeight: 30
                                fontSize: 12
                                onClicked: bridge.loadInstanceMods(installedPopup.current.id || "")
                            }
                        }

                        ListView {
                            id: instModList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            spacing: 6
                            model: bridge.instanceModsModel
                            boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                            delegate: Rectangle {
                                id: instModRow
                                required property var modelData
                                width: instModList.width
                                height: 44
                                radius: 9
                                color: theme.surfaceAlt
                                opacity: (modelData.enabled === true) ? 1.0 : 0.55

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 8
                                    spacing: 8

                                    Rectangle {
                                        width: 7
                                        height: 7
                                        radius: 4
                                        color: (modelData.enabled === true) ? theme.accent : theme.text3
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 1

                                        Text {
                                            Layout.fillWidth: true
                                            text: (modelData.titleZh || "").length > 0
                                                  ? modelData.titleZh
                                                  : (modelData.title || modelData.file || "")
                                            font.pixelSize: 12
                                            color: theme.text1
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            text: modelData.file || ""
                                            font.pixelSize: 10
                                            color: theme.text3
                                            elide: Text.ElideMiddle
                                        }
                                    }

                                    SproutButton {
                                        text: (modelData.enabled === true) ? "禁用" : "启用"
                                        primary: false
                                        active: true
                                        implicitHeight: 26
                                        fontSize: 11
                                        onClicked: bridge.toggleInstanceMod(installedPopup.current.id || "", modelData.file || "")
                                    }
                                }
                            }

                            Text {
                                anchors.centerIn: parent
                                visible: instModList.count === 0
                                width: instModList.width - 40
                                horizontalAlignment: Text.AlignHCenter
                                text: "该实例还没有模组。点右上角「安装模组…」选择本地 jar，或到模组栏目按版本下载。"
                                font.pixelSize: 11
                                color: theme.text3
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }

                SproutButton {
                    Layout.fillWidth: true
                    text: "设为启动目标"
                    primary: false
                    implicitHeight: 42
                    fontSize: 13
                    onClicked: {
                        bridge.setLaunchChoice(installedPopup.current.id || "");
                        installedPopup.close();
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    SproutButton {
                        text: "启动游戏"
                        primary: true
                        active: !bridge.busy && !bridge.running
                        implicitHeight: 40
                        fontSize: 13
                        onClicked: {
                            bridge.setLaunchChoice(installedPopup.current.id || "");
                            bridge.launchChosen();
                            installedPopup.close();
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: "内存 " + bridge.memoryMb + " MB"
                        font.pixelSize: 11
                        color: theme.text3
                    }
                }
            }
        }
    }
}
