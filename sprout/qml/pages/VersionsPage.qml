import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: page
    objectName: "versionsPage"

    property string tab: "versions"

    // ---------------------------------------------------------- 视图切换
    RowLayout {
        id: tabRow
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: 26
        anchors.rightMargin: 22
        height: 36
        spacing: 8

        Repeater {
            model: [
                { key: "versions", label: "版本清单" },
                { key: "instances", label: "我的实例" },
                { key: "saves", label: "存档世界" }
            ]

            SproutButton {
                text: modelData.label
                primary: page.tab === modelData.key
                implicitHeight: 36
                fontSize: 13
                onClicked: page.tab = modelData.key
            }
        }

        Item { Layout.fillWidth: true }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 26
        anchors.rightMargin: 22
        anchors.topMargin: 48
        anchors.bottomMargin: 8
        spacing: 12
        visible: page.tab === "versions"

        // ---------------------------------------------------------- 工具条
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Rectangle {
                Layout.preferredWidth: 260
                Layout.preferredHeight: 36
                radius: 10
                color: theme.surfaceAlt
                border.width: 1
                border.color: searchField.activeFocus ? theme.accent : "transparent"
                Behavior on border.color { ColorAnimation { duration: 160 } }

                TextField {
                    id: searchField
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    background: Item {}
                    placeholderText: "搜索版本号，例如 1.21"
                    placeholderTextColor: theme.text3
                    color: theme.text1
                    font.pixelSize: 13
                    verticalAlignment: TextInput.AlignVCenter
                    onTextChanged: bridge.setSearchText(text)
                }
            }

            Repeater {
                model: [
                    { key: "all", label: "全部" },
                    { key: "release", label: "正式版" },
                    { key: "snapshot", label: "快照" }
                ]

                SproutButton {
                    text: modelData.label
                    primary: modelData.key === "all"
                             ? (bridge.typeFilter.length === 0 || bridge.typeFilter === "all")
                             : bridge.typeFilter === modelData.key
                    implicitHeight: 36
                    fontSize: 13
                    onClicked: bridge.setTypeFilter(modelData.key)
                }
            }

            Item { Layout.fillWidth: true }

            SproutButton {
                text: "刷新清单"
                primary: false
                active: !bridge.busy
                implicitHeight: 36
                fontSize: 13
                onClicked: bridge.refreshVersions()
            }
        }

        Text {
            Layout.fillWidth: true
            text: "这里只列出尚未安装、可直接下载的版本；已安装的游戏在首页或「我的实例」里启动"
            font.pixelSize: 11
            color: theme.text3
        }

        // ------------------------------------------------------------ 列表
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 8
            // 版本库只用于下载新版本：已安装的版本不出现在这里
            model: bridge.libraryModel
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            add: Transition {
                ParallelAnimation {
                    NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 260; easing.type: Easing.OutCubic }
                    NumberAnimation { property: "y"; from: 18; to: 0; duration: 300; easing.type: Easing.OutQuint }
                }
            }

            delegate: Rectangle {
                id: cardRow
                required property int index
                required property string id
                required property string type
                required property string releaseTime
                required property bool installed
                required property bool isLatest
                required property int javaMajor

                width: ListView.view.width
                height: 62
                radius: 12
                color: theme.card
                border.width: 1
                border.color: hover.containsMouse ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.5) : theme.border
                Behavior on border.color { ColorAnimation { duration: 160 } }
                scale: hover.containsMouse ? 1.004 : 1.0
                Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

                opacity: 0
                Component.onCompleted: {
                    enterDelay.interval = Math.min(index * 18, 420);
                    enterDelay.start();
                }
                Timer { id: enterDelay; onTriggered: enterAnim.start() }
                NumberAnimation {
                    id: enterAnim
                    target: cardRow
                    property: "opacity"
                    to: 1.0
                    duration: 300
                    easing.type: Easing.OutCubic
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 14
                    spacing: 12

                    Rectangle {
                        width: 34
                        height: 34
                        radius: 17
                        color: cardRow.installed ? theme.accentSoft : theme.surfaceAlt
                        Text {
                            anchors.centerIn: parent
                            text: cardRow.type === "snapshot" ? "S" : "R"
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            color: cardRow.installed ? theme.accent : theme.text3
                        }
                    }

                    Column {
                        Layout.fillWidth: true
                        spacing: 3

                        Row {
                            spacing: 8
                            Text {
                                text: cardRow.id
                                font.pixelSize: 14
                                font.weight: Font.DemiBold
                                color: theme.text1
                            }
                            Rectangle {
                                visible: cardRow.isLatest
                                width: 32
                                height: 15
                                radius: 8
                                color: theme.accentSoft
                                Text {
                                    anchors.centerIn: parent
                                    text: "最新"
                                    font.pixelSize: 9
                                    color: theme.accent
                                }
                            }
                        }

                        Text {
                            text: (cardRow.type === "snapshot" ? "快照" : "正式版")
                                  + " · " + cardRow.releaseTime
                                  + " · 需要 Java " + cardRow.javaMajor
                            font.pixelSize: 11
                            color: theme.text3
                        }
                    }

                    Text {
                        text: cardRow.installed ? "已安装" : "未安装"
                        font.pixelSize: 11
                        color: cardRow.installed ? theme.accent : theme.text3
                    }

                    SproutButton {
                        text: "重装"
                        visible: cardRow.installed
                        primary: false
                        active: !bridge.busy
                        implicitHeight: 32
                        fontSize: 12
                        onClicked: {
                            loaderPopup.reset(cardRow.id);
                            loaderPopup.open();
                        }
                    }

                    SproutButton {
                        text: cardRow.installed ? "启动" : "安装"
                        primary: true
                        active: !bridge.busy
                        implicitHeight: 32
                        fontSize: 12
                        onClicked: {
                            if (cardRow.installed) {
                                bridge.launchVersion(cardRow.id);
                            } else {
                                loaderPopup.reset(cardRow.id);
                                loaderPopup.open();
                            }
                        }
                    }
                }

                MouseArea {
                    id: hover
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.NoButton
                }
            }

            Text {
                anchors.centerIn: parent
                visible: list.count === 0 && !bridge.busy
                text: "没有匹配的版本"
                font.pixelSize: 13
                color: theme.text3
            }
        }
    }

    // ------------------------------------------------------------ 实例列表
    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 26
        anchors.rightMargin: 22
        anchors.topMargin: 48
        anchors.bottomMargin: 8
        spacing: 12
        visible: page.tab === "instances"

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Text {
                text: "每个实例拥有独立的游戏目录与 mod 存放位置，版本互不干扰"
                font.pixelSize: 12
                color: theme.text3
            }

            Item { Layout.fillWidth: true }

            SproutButton {
                text: "新建实例"
                primary: true
                active: !bridge.busy
                implicitHeight: 36
                fontSize: 13
                onClicked: {
                    loaderPopup.reset("");
                    loaderPopup.open();
                }
            }
        }

        ListView {
            id: instList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 8
            model: bridge.instancesModel
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                id: instRow
                required property int index
                required property string id
                required property string name
                required property string versionId
                required property string loader
                required property var playtime
                required property string gameDir

                width: instList.width
                height: 68
                radius: 12
                color: theme.card
                border.width: 1
                border.color: instHover.containsMouse ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.5) : theme.border
                Behavior on border.color { ColorAnimation { duration: 160 } }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 14
                    spacing: 14

                    Rectangle {
                        width: 34
                        height: 34
                        radius: 17
                        color: theme.accentSoft
                        Text {
                            anchors.centerIn: parent
                            text: instRow.loader === "fabric" ? "F"
                                  : instRow.loader === "forge" ? "Fg"
                                  : instRow.loader === "neoforge" ? "N"
                                  : instRow.loader === "quilt" ? "Q" : "V"
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            color: theme.accent
                        }
                    }

                    Column {
                        Layout.fillWidth: true
                        spacing: 3

                        Row {
                            spacing: 8
                            Text {
                                text: instRow.name
                                font.pixelSize: 14
                                font.weight: Font.DemiBold
                                color: theme.text1
                            }
                            Rectangle {
                                width: 46
                                height: 15
                                radius: 8
                                color: theme.surfaceAlt
                                Text {
                                    anchors.centerIn: parent
                                    text: instRow.loader.length > 0 ? instRow.loader : "vanilla"
                                    font.pixelSize: 9
                                    color: theme.text3
                                }
                            }
                        }

                        Text {
                            text: instRow.versionId + " · 游戏时长 "
                                  + (Math.round((instRow.playtime || 0) / 60)) + " 分钟"
                            font.pixelSize: 11
                            color: theme.text3
                        }
                    }

                    SproutButton {
                        text: "打开目录"
                        primary: false
                        implicitHeight: 32
                        fontSize: 12
                        onClicked: bridge.openPath(instRow.gameDir)
                    }

                    SproutButton {
                        text: "移除"
                        primary: false
                        implicitHeight: 32
                        fontSize: 12
                        onClicked: bridge.removeInstance(instRow.id)
                    }

                    SproutButton {
                        text: "启动"
                        primary: true
                        active: !bridge.running
                        implicitHeight: 32
                        fontSize: 12
                        onClicked: bridge.launchInstance(instRow.id)
                    }
                }

                MouseArea {
                    id: instHover
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.NoButton
                }
            }

            Text {
                anchors.centerIn: parent
                visible: instList.count === 0
                text: "还没有实例，点右上角安装一个加载器就会自动生成"
                font.pixelSize: 13
                color: theme.text3
            }
        }
    }

    // ------------------------------------------------------ 存档世界
    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 26
        anchors.rightMargin: 22
        anchors.topMargin: 48
        anchors.bottomMargin: 8
        spacing: 12
        visible: page.tab === "saves"

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Text {
                Layout.fillWidth: true
                text: "已扫描到 " + bridge.savesCount + " 个存档世界，来自 .minecraft 与各实例目录"
                font.pixelSize: 12
                color: theme.text3
                elide: Text.ElideRight
            }

            SproutButton {
                text: "重新扫描"
                implicitHeight: 36
                fontSize: 13
                active: !bridge.busy
                onClicked: bridge.refreshSaves()
            }
        }

        ListView {
            id: saveList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 8
            model: bridge.savesModel
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                id: saveRow
                required property int index
                required property string name
                required property string folder
                required property string path
                required property string gameDir
                required property string source
                required property string versionId
                required property string versionName
                required property string lastPlayedText
                required property string sizeText
                required property string iconUrl
                required property bool quick
                width: saveList.width
                height: 76
                radius: 12
                color: theme.card
                border.width: 1
                border.color: saveHover.containsMouse ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.5) : theme.border
                Behavior on border.color { ColorAnimation { duration: 160 } }

                HoverHandler { id: saveHover }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    spacing: 12

                    Rectangle {
                        width: 46
                        height: 46
                        radius: 8
                        color: theme.surfaceAlt
                        clip: true
                        Image {
                            anchors.fill: parent
                            source: saveRow.iconUrl
                            visible: saveRow.iconUrl.length > 0
                            fillMode: Image.PreserveAspectCrop
                            sourceSize.width: 92
                            sourceSize.height: 92
                            asynchronous: true
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: saveRow.iconUrl.length === 0
                            text: "世"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: theme.accent
                        }
                    }

                    Column {
                        Layout.fillWidth: true
                        spacing: 4

                        Text {
                            width: parent.width
                            text: saveRow.name
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: theme.text1
                            elide: Text.ElideRight
                        }

                        Text {
                            width: parent.width
                            text: saveRow.source
                                  + " · " + (saveRow.versionId.length > 0 ? saveRow.versionId : (saveRow.versionName.length > 0 ? saveRow.versionName : "版本未知"))
                                  + " · " + saveRow.lastPlayedText
                                  + (saveRow.sizeText.length > 0 ? " · " + saveRow.sizeText : "")
                            font.pixelSize: 11
                            color: theme.text3
                            elide: Text.ElideRight
                        }
                    }

                    SproutButton {
                        text: "打开目录"
                        implicitHeight: 32
                        fontSize: 12
                        onClicked: bridge.openSaveFolder(saveRow.path)
                    }

                    SproutButton {
                        text: saveRow.quick ? "直接进入" : "启动游戏"
                        primary: saveRow.quick
                        implicitHeight: 32
                        fontSize: 12
                        active: !bridge.running && !bridge.busy
                        onClicked: bridge.launchSave(saveRow.path)
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: saveList.count === 0
                text: "没扫到存档。若世界在别的目录，从对应实例里启动一次游戏就会出现在这里"
                font.pixelSize: 13
                color: theme.text3
            }
        }
    }

    // ------------------------------------------------------ 加载器安装面板
    Popup {
        id: loaderPopup
        objectName: "loaderPopup"
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape
        anchors.centerIn: parent
        width: 560

        property string loaderKind: "fabric"
        property string gameVer: ""
        property string picked: ""
        property bool loading: false
        property var found: []
        property string hint: ""

        function reset(game) {
            gameVer = game || "";
            loaderKind = "vanilla";
            found = [];
            picked = "";
            loading = false;
            hint = "选原版则不安装任何加载器，装完就是纯净版本";
        }

        onOpened: {
            if (gameVer.length === 0) {
                if (bridge.latestRelease && bridge.latestRelease.length > 0)
                    gameVer = bridge.latestRelease;
                else if (bridge.featured && bridge.featured.id)
                    gameVer = String(bridge.featured.id);
            }
        }

        Connections {
            target: bridge

            function onVersionsChanged() {
                if (loaderPopup.visible && loaderPopup.gameVer.length === 0) {
                    if (bridge.latestRelease && bridge.latestRelease.length > 0)
                        loaderPopup.gameVer = bridge.latestRelease;
                    else if (bridge.featured && bridge.featured.id)
                        loaderPopup.gameVer = String(bridge.featured.id);
                }
            }

            function onLoaderVersionsReady(loader, game, versions) {
                if (loader !== loaderPopup.loaderKind || game !== loaderPopup.gameVer)
                    return;
                loaderPopup.loading = false;
                loaderPopup.found = versions;
                loaderPopup.picked = versions.length > 0 ? versions[0] : "";
                loaderPopup.hint = versions.length > 0
                        ? ("共 " + versions.length + " 个版本，默认选中最新的一个")
                        : "该游戏版本没有可用的加载器版本";
            }
        }

        background: Rectangle {
            radius: 16
            color: theme.card
            border.width: 1
            border.color: theme.border
        }

        contentItem: ColumnLayout {
            spacing: 13

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 22
                Layout.rightMargin: 16
                Layout.topMargin: 18
                spacing: 10

                Text {
                    text: "安装模组加载器"
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                    color: theme.text1
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    Layout.preferredWidth: 26
                    Layout.preferredHeight: 26
                    radius: 13
                    color: closeHover.containsMouse ? theme.surfaceAlt : "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: "✕"
                        font.pixelSize: 12
                        color: theme.text3
                    }

                    MouseArea {
                        id: closeHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: loaderPopup.close()
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                Layout.leftMargin: 22
                Layout.rightMargin: 22
                text: "选择游戏版本与加载器，安装完成后会自动生成对应实例，可直接在该实例下装模组。"
                wrapMode: Text.WordWrap
                font.pixelSize: 12
                color: theme.text3
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 22
                Layout.rightMargin: 22
                spacing: 10

                Text {
                    text: "游戏版本"
                    font.pixelSize: 13
                    color: theme.text2
                }

                Rectangle {
                    Layout.preferredWidth: 170
                    Layout.preferredHeight: 34
                    radius: 9
                    color: theme.surfaceAlt
                    border.width: 1
                    border.color: verField.activeFocus ? theme.accent : "transparent"

                    TextField {
                        id: verField
                        anchors.fill: parent
                        anchors.leftMargin: 11
                        anchors.rightMargin: 11
                        background: Item {}
                        placeholderText: "例如 1.21.4"
                        placeholderTextColor: theme.text3
                        color: theme.text1
                        font.pixelSize: 13
                        verticalAlignment: TextInput.AlignVCenter
                        text: loaderPopup.gameVer
                        onTextChanged: {
                            loaderPopup.gameVer = text.trim();
                            loaderPopup.found = [];
                            loaderPopup.picked = "";
                        }
                    }
                }

                Item { Layout.fillWidth: true }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 22
                Layout.rightMargin: 22
                spacing: 8

                Repeater {
                    model: [
                        { key: "vanilla", label: "原版" },
                        { key: "fabric", label: "Fabric" },
                        { key: "quilt", label: "Quilt" },
                        { key: "neoforge", label: "NeoForge" },
                        { key: "forge", label: "Forge" }
                    ]

                    SproutButton {
                        text: modelData.label
                        primary: loaderPopup.loaderKind === modelData.key
                        implicitHeight: 32
                        fontSize: 12
                        onClicked: {
                            loaderPopup.loaderKind = modelData.key;
                            loaderPopup.found = [];
                            loaderPopup.picked = "";
                            loaderPopup.hint = "";
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                SproutButton {
                    text: "查询加载器版本"
                    primary: false
                    visible: loaderPopup.loaderKind !== "vanilla"
                    active: !loaderPopup.loading && loaderPopup.gameVer.length > 0
                    implicitHeight: 32
                    fontSize: 12
                    onClicked: {
                        loaderPopup.loading = true;
                        loaderPopup.hint = "正在查询 " + loaderPopup.loaderKind + " 版本…";
                        bridge.fetchLoaderVersions(loaderPopup.loaderKind, loaderPopup.gameVer);
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 22
                Layout.rightMargin: 22
                Layout.preferredHeight: 96
                radius: 10
                color: theme.surfaceAlt
                visible: loaderPopup.loaderKind === "vanilla"

                Text {
                    anchors.centerIn: parent
                    width: parent.width - 40
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: "原版模式：只安装游戏本体，不装任何加载器。之后想装模组可以再来这里选 Fabric / Forge 等。"
                    font.pixelSize: 12
                    color: theme.text3
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 22
                Layout.rightMargin: 22
                Layout.preferredHeight: 196
                radius: 10
                color: theme.surfaceAlt
                clip: true
                visible: loaderPopup.loaderKind !== "vanilla"

                ListView {
                    id: verList
                    anchors.fill: parent
                    anchors.margins: 6
                    clip: true
                    spacing: 4
                    model: loaderPopup.found
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    delegate: Rectangle {
                        width: verList.width
                        height: 30
                        radius: 7
                        color: loaderPopup.picked === modelData ? theme.accentSoft : "transparent"

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: 10
                            text: modelData
                            font.family: "Consolas"
                            font.pixelSize: 12
                            color: loaderPopup.picked === modelData ? theme.accent : theme.text2
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: loaderPopup.picked = modelData
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: loaderPopup.found.length === 0
                    text: loaderPopup.loading ? "查询中…" : "先选好游戏版本再查询可用加载器版本"
                    font.pixelSize: 12
                    color: theme.text3
                }
            }

            Text {
                Layout.fillWidth: true
                Layout.leftMargin: 22
                Layout.rightMargin: 22
                text: loaderPopup.hint
                wrapMode: Text.WordWrap
                font.pixelSize: 11
                color: theme.text3
                visible: loaderPopup.hint.length > 0
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 22
                Layout.rightMargin: 22
                Layout.bottomMargin: 20
                spacing: 10

                Text {
                    text: loaderPopup.loaderKind === "vanilla"
                          ? ("将安装 " + loaderPopup.gameVer + " 原版 · 不安装任何加载器")
                          : (loaderPopup.picked.length > 0
                             ? ("将安装 " + loaderPopup.gameVer + " · " + loaderPopup.loaderKind + " " + loaderPopup.picked)
                             : "尚未选择加载器版本")
                    font.pixelSize: 11
                    color: theme.text3
                }

                Item { Layout.fillWidth: true }

                SproutButton {
                    text: "取消"
                    primary: false
                    implicitHeight: 34
                    fontSize: 12
                    onClicked: loaderPopup.close()
                }

                SproutButton {
                    text: "开始安装"
                    primary: true
                    active: !bridge.busy && loaderPopup.gameVer.length > 0
                            && (loaderPopup.loaderKind === "vanilla" || loaderPopup.picked.length > 0)
                    implicitHeight: 34
                    fontSize: 12
                    onClicked: {
                        if (loaderPopup.loaderKind === "vanilla")
                            bridge.installVersion(loaderPopup.gameVer);
                        else
                            bridge.installWithLoader(loaderPopup.gameVer, loaderPopup.loaderKind, loaderPopup.picked);
                        loaderPopup.close();
                    }
                }
            }
        }
    }
}
