import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: page

    property int tab: 0
    property string modKind: "mod"
    property string selectedVersion: ""
    // 实例筛选（装载模组带入）：用页面局部状态承载，避免跨页面时序导致的绑定不刷新
    property string instFilterLabel: ""
    property string instFilterTarget: ""
    property bool instFilterMissing: false
    property bool instFilterActive: instFilterLabel.length > 0

    function syncInstFilter() {
        page.instFilterLabel = bridge.modFilterLabel;
        page.instFilterTarget = bridge.modTarget;
        page.instFilterMissing = bridge.modLoaderMissing;
    }

    onVisibleChanged: {
        if (visible)
            syncInstFilter();
    }
    readonly property string currentDetailId: (bridge.modDetail && bridge.modDetail.id !== undefined)
                                               ? bridge.modDetail.id : ""
    readonly property bool detailOpen: currentDetailId.length > 0
    readonly property string activeVersion: selectedVersion.length > 0 ? selectedVersion
                                                                       : bridge.detailDefaultVersion

    onCurrentDetailIdChanged: selectedVersion = ""

    function fmtDate(text) {
        return (text || "").substring(0, 10);
    }

    function downloadVersion(versionId) {
        if (!versionId || versionId.length === 0)
            return;
        var dir = bridge.chooseDir("选择下载位置", bridge.modsPath());
        if (dir.length === 0)
            return;
        bridge.checkDepsAndDownload(versionId, dir);
    }

    // 打开页面就直接给一份热门列表，不必先搜索
    Component.onCompleted: {
        syncInstFilter();
        bridge.searchMods("", page.modKind);
    }
    onTabChanged: {
        if (page.tab === 0 && bridge.searchTotal === 0 && !bridge.searchLoading)
            bridge.searchMods("", page.modKind);
    }

    function fmtCount(n) {
        var v = Number(n);
        if (isNaN(v))
            return "0";
        if (v >= 1000000)
            return (v / 1000000).toFixed(1) + "M";
        if (v >= 1000)
            return (v / 1000).toFixed(1) + "k";
        return String(v);
    }

    function fmtSize(n) {
        var v = Number(n);
        if (isNaN(v))
            return "";
        if (v >= 1048576)
            return (v / 1048576).toFixed(1) + " MB";
        if (v >= 1024)
            return Math.round(v / 1024) + " KB";
        return v + " B";
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 26
        anchors.rightMargin: 22
        anchors.topMargin: 4
        anchors.bottomMargin: 8
        spacing: 12

        // ------------------------------------------------------ 顶部切换
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Repeater {
                model: [
                    { key: 0, label: "模组市场" },
                    { key: 1, label: "已安装" }
                ]

                SproutButton {
                    required property var modelData
                    text: modelData.label
                    primary: page.tab === modelData.key
                    implicitHeight: 34
                    fontSize: 13
                    onClicked: {
                        page.tab = modelData.key;
                        if (page.tab === 1)
                            bridge.refreshMods();
                    }
                }
            }

            Rectangle {
                Layout.preferredHeight: 24
                Layout.preferredWidth: targetText.implicitWidth + 22
                radius: 12
                color: theme.surfaceAlt
                visible: bridge.modTarget.length > 0
                Text {
                    id: targetText
                    anchors.centerIn: parent
                    text: "目标实例 " + bridge.modTarget
                    font.pixelSize: 11
                    color: theme.text3
                }
            }

            Item { Layout.fillWidth: true }
        }

        // ------------------------------------------------------ 市场工具栏
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            visible: page.tab === 0

            Rectangle {
                Layout.preferredWidth: 190
                Layout.preferredHeight: 36
                radius: 10
                color: theme.surfaceAlt
                border.width: 1
                border.color: marketField.activeFocus ? theme.accent : "transparent"
                Behavior on border.color { ColorAnimation { duration: 160 } }

                TextField {
                    id: marketField
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    background: Item {}
                    placeholderText: "搜索模组，留空按热度列出"
                    placeholderTextColor: theme.text3
                    color: theme.text1
                    font.pixelSize: 13
                    verticalAlignment: TextInput.AlignVCenter
                    onAccepted: bridge.searchMods(text, page.modKind)
                }
            }

            SproutButton {
                text: "搜索"
                primary: true
                active: !bridge.searchLoading
                implicitHeight: 36
                fontSize: 13
                onClicked: bridge.searchMods(marketField.text, page.modKind)
            }

            Repeater {
                model: [
                    { key: "mod", label: "模组" },
                    { key: "shader", label: "光影" },
                    { key: "resourcepack", label: "资源包" },
                    { key: "modpack", label: "整合包" }
                ]

                SproutButton {
                    required property var modelData
                    text: modelData.label
                    primary: page.modKind === modelData.key
                    implicitHeight: 36
                    fontSize: 12
                    onClicked: {
                        page.modKind = modelData.key;
                        bridge.searchMods(marketField.text, modelData.key);
                    }
                }
            }

            Item { Layout.fillWidth: true }

            Repeater {
                model: [
                    { key: "modrinth", label: "Modrinth" },
                    { key: "curseforge", label: "CurseForge" }
                ]

                SproutButton {
                    required property var modelData
                    text: modelData.label
                    primary: bridge.modSource === modelData.key
                    implicitHeight: 32
                    fontSize: 11
                    onClicked: {
                        if (bridge.modSource !== modelData.key)
                            bridge.setModSource(modelData.key);
                        bridge.searchMods(marketField.text, page.modKind);
                    }
                }
            }

            Text {
                text: bridge.searchLoading
                      ? "正在加载…"
                      : (marketField.text.length > 0
                         ? ("共 " + bridge.searchTotal + " 个结果")
                         : ("热门排行 · 共 " + bridge.searchTotal + " 个"))
                font.pixelSize: 11
                color: theme.text3
                elide: Text.ElideRight
                Layout.maximumWidth: 132
            }
        }

        Text {
            Layout.fillWidth: true
            visible: bridge.modSource === "curseforge" && !bridge.cfReady
            text: "CurseForge 未配置 API Key：请到 设置 → 模组来源 填入后即可搜索与下载（当前会给出提示而非报错）"
            font.pixelSize: 11
            color: theme.accent
            wrapMode: Text.WordWrap
        }

        // -------------------------------------------- 实例筛选提示（装载模组带入）
        Rectangle {
            id: filterBar
            objectName: "modFilterBar"
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 36 : 0
            visible: page.tab === 0 && page.instFilterActive
            radius: 10
            color: theme.surfaceAlt

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 8
                spacing: 8

                Text {
                    text: page.instFilterLabel.indexOf("筛选") === 0
                          ? page.instFilterLabel
                          : ("筛选：" + page.instFilterLabel)
                    font.pixelSize: 11
                    color: theme.text2
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                Rectangle {
                    visible: page.instFilterMissing
                    width: loaderWarn.implicitWidth + 16
                    height: 20
                    radius: 10
                    color: theme.accentSoft

                    Text {
                        id: loaderWarn
                        anchors.centerIn: parent
                        text: "该实例未安装模组加载器"
                        font.pixelSize: 10
                        color: theme.accent
                    }
                }

                SproutButton {
                    visible: page.instFilterMissing
                    text: "装加载器"
                    primary: true
                    active: !bridge.busy
                    implicitHeight: 26
                    fontSize: 11
                    onClicked: bridge.requestModsForInstance(page.instFilterTarget)
                }

                SproutButton {
                    text: "清除"
                    primary: false
                    active: true
                    implicitHeight: 26
                    fontSize: 11
                    onClicked: bridge.clearModFilter()
                }
            }
        }

        // ------------------------------------------------------ 已装工具栏
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            visible: page.tab === 1

            SproutButton {
                text: "刷新列表"
                primary: false
                active: !bridge.busy
                implicitHeight: 34
                fontSize: 12
                onClicked: bridge.refreshMods()
            }

            SproutButton {
                text: "检查更新"
                primary: false
                active: !bridge.busy
                implicitHeight: 34
                fontSize: 12
                onClicked: bridge.checkModUpdates()
            }

            SproutButton {
                text: "全部更新"
                primary: true
                active: !bridge.busy
                implicitHeight: 34
                fontSize: 12
                onClicked: bridge.updateAllMods()
            }

            Item { Layout.fillWidth: true }

            SproutButton {
                text: "打开目录"
                primary: false
                active: true
                implicitHeight: 34
                fontSize: 12
                onClicked: bridge.openPath(bridge.modsPath())
            }

            SproutButton {
                text: "导入整合包"
                primary: false
                active: !bridge.busy
                implicitHeight: 34
                fontSize: 12
                onClicked: {
                    var p = bridge.pickFile("选择整合包", "整合包 (*.zip *.mrpack);;所有文件 (*)");
                    if (p.length > 0)
                        bridge.importModpack(p);
                }
            }

            SproutButton {
                text: "导出整合包"
                primary: false
                active: !bridge.busy
                implicitHeight: 34
                fontSize: 12
                onClicked: {
                    var p = bridge.pickSaveFile("导出整合包", "压缩包 (*.zip)", "sprout-pack.zip");
                    if (p.length > 0)
                        bridge.exportModpack(p);
                }
            }
        }

        // -------------------------------------------------------- 市场列表
        ListView {
            id: marketList
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: page.tab === 0
            clip: true
            spacing: 8
            model: bridge.searchModel
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            add: Transition {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 240; easing.type: Easing.OutCubic }
            }

            delegate: Rectangle {
                id: marketRow
                required property int index
                required property string id
                required property string title
                required property string titleZh
                required property string description
                required property string iconUrl
                required property var downloads
                required property string author
                required property string projectType
                required property var installed

                width: ListView.view.width
                height: 74
                radius: 12
                color: theme.card
                border.width: 1
                border.color: marketHover.containsMouse ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.5) : theme.border
                Behavior on border.color { ColorAnimation { duration: 160 } }
                scale: marketHover.containsMouse ? 1.003 : 1.0
                Behavior on scale { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    spacing: 12

                    Rectangle {
                        Layout.preferredWidth: 46
                        Layout.preferredHeight: 46
                        radius: 10
                        color: theme.surfaceAlt
                        clip: true

                        Image {
                            anchors.fill: parent
                            source: marketRow.iconUrl
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            visible: status === Image.Ready
                            sourceSize.width: 92
                            sourceSize.height: 92
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: marketRow.iconUrl.length === 0
                            text: marketRow.title.length > 0 ? marketRow.title.charAt(0) : "M"
                            font.pixelSize: 16
                            color: theme.text3
                        }
                    }

                    Column {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 50
                        spacing: 4

                        Row {
                            width: parent.width
                            spacing: 6

                            Text {
                                text: marketRow.titleZh.length > 0 ? marketRow.titleZh : marketRow.title
                                font.pixelSize: 14
                                font.weight: Font.DemiBold
                                color: theme.text1
                                elide: Text.ElideRight
                                width: Math.min(implicitWidth, parent.width * (marketRow.titleZh.length > 0 ? 0.62 : 1.0))
                            }

                            Text {
                                visible: marketRow.titleZh.length > 0
                                text: marketRow.title
                                font.pixelSize: 11
                                color: theme.text3
                                elide: Text.ElideRight
                                width: Math.min(implicitWidth, parent.width * 0.34)
                            }
                        }

                        Text {
                            width: parent.width
                            text: marketRow.description
                            font.pixelSize: 11
                            color: theme.text3
                            elide: Text.ElideRight
                            maximumLineCount: 1
                        }

                        Text {
                            text: marketRow.author
                                  + " · 下载 " + page.fmtCount(marketRow.downloads)
                                  + " · " + marketRow.projectType
                            font.pixelSize: 10
                            color: theme.text3
                            elide: Text.ElideRight
                            width: parent.width
                        }
                    }

                    Text {
                        text: marketRow.installed ? "已安装" : "›"
                        font.pixelSize: marketRow.installed ? 11 : 20
                        color: marketRow.installed ? theme.accent : theme.text3
                    }
                }

                MouseArea {
                    id: marketHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: bridge.openModDetail(marketRow.id)
                }
            }

            footer: Item {
                width: marketList.width
                height: marketList.count > 0 ? 56 : 0

                SproutButton {
                    anchors.centerIn: parent
                    visible: marketList.count > 0 && marketList.count < bridge.searchTotal
                    text: bridge.searchLoading ? "加载中…" : "加载更多"
                    primary: false
                    active: !bridge.searchLoading
                    implicitHeight: 34
                    fontSize: 12
                    onClicked: bridge.loadMoreMods()
                }
            }

            Text {
                anchors.centerIn: parent
                visible: marketList.count === 0
                text: bridge.searchLoading ? "正在搜索…" : "没有结果，换个关键词试试"
                font.pixelSize: 13
                color: theme.text3
            }
        }

        // -------------------------------------------------------- 已装列表
        ListView {
            id: modList
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: page.tab === 1
            clip: true
            spacing: 8
            model: bridge.modsModel
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            add: Transition {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 240; easing.type: Easing.OutCubic }
            }

            delegate: Rectangle {
                id: modRow
                required property int index
                required property string file
                required property string title
                required property string titleZh
                required property var size
                required property var enabled
                required property var hasUpdate
                required property string latestVersion
                required property string source

                width: ListView.view.width
                height: 58
                radius: 12
                color: theme.card
                border.width: 1
                border.color: modHover.containsMouse ? Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.45) : theme.border
                Behavior on border.color { ColorAnimation { duration: 160 } }
                opacity: modRow.enabled ? 1.0 : 0.55

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 14
                    spacing: 12

                    Rectangle {
                        width: 8
                        height: 8
                        radius: 4
                        color: modRow.enabled ? theme.accent : theme.text3
                    }

                    Column {
                        Layout.fillWidth: true
                        spacing: 3

                        Row {
                            spacing: 8
                            Text {
                                text: modRow.titleZh.length > 0
                                      ? modRow.titleZh
                                      : (modRow.title.length > 0 ? modRow.title : modRow.file)
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                color: theme.text1
                                elide: Text.ElideRight
                                width: Math.min(implicitWidth, modRow.titleZh.length > 0 ? 300 : 460)
                            }

                            Text {
                                visible: modRow.titleZh.length > 0
                                text: modRow.title.length > 0 ? modRow.title : modRow.file
                                font.pixelSize: 11
                                color: theme.text3
                                elide: Text.ElideRight
                                width: Math.min(implicitWidth, 220)
                            }

                            Rectangle {
                                visible: modRow.hasUpdate
                                width: 40
                                height: 15
                                radius: 8
                                color: theme.accentSoft
                                Text {
                                    anchors.centerIn: parent
                                    text: "可更新"
                                    font.pixelSize: 9
                                    color: theme.accent
                                }
                            }
                        }

                        Text {
                            text: modRow.file + (page.fmtSize(modRow.size).length > 0 ? " · " + page.fmtSize(modRow.size) : "")
                            font.pixelSize: 10
                            color: theme.text3
                            elide: Text.ElideRight
                            width: parent.width
                        }
                    }

                    Text {
                        text: modRow.enabled ? "已启用" : "已禁用"
                        font.pixelSize: 11
                        color: modRow.enabled ? theme.accent : theme.text3
                    }

                    SproutButton {
                        text: modRow.enabled ? "禁用" : "启用"
                        primary: false
                        active: true
                        implicitHeight: 30
                        fontSize: 12
                        onClicked: bridge.toggleMod(modRow.file)
                    }

                    SproutButton {
                        text: "删除"
                        primary: false
                        active: true
                        implicitHeight: 30
                        fontSize: 12
                        onClicked: bridge.removeMod(modRow.file)
                    }
                }

                MouseArea {
                    id: modHover
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.NoButton
                }
            }

            Text {
                anchors.centerIn: parent
                visible: modList.count === 0
                text: "目标实例下还没有模组，去市场逛逛"
                font.pixelSize: 13
                color: theme.text3
            }
        }
    }

    // ============================================================ 加载遮罩
    Rectangle {
        id: loadingMask
        anchors.fill: parent
        z: 40
        visible: bridge.searchLoading && page.tab === 0 && !page.detailOpen
        color: Qt.rgba(theme.bg.r, theme.bg.g, theme.bg.b, 0.86)
        opacity: visible ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 160 } }

        Column {
            anchors.centerIn: parent
            spacing: 16

            Item {
                id: spinner
                width: 46
                height: 46
                anchors.horizontalCenter: parent.horizontalCenter

                Rectangle {
                    anchors.fill: parent
                    radius: width / 2
                    color: "transparent"
                    border.width: 3
                    border.color: Qt.rgba(theme.accent.r, theme.accent.g, theme.accent.b, 0.22)
                }
                Rectangle {
                    width: 10
                    height: 10
                    radius: 5
                    color: theme.accent
                    x: spinner.width / 2 - 5
                    y: -1
                }

                RotationAnimator on rotation {
                    from: 0
                    to: 360
                    duration: 900
                    loops: Animation.Infinite
                    running: loadingMask.visible
                }
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "正在加载" + (page.modKind === "shader" ? "光影"
                                    : page.modKind === "resourcepack" ? "资源包"
                                    : page.modKind === "modpack" ? "整合包" : "模组") + "…"
                font.pixelSize: 13
                color: theme.text2
            }

            Column {
                spacing: 6
                Repeater {
                    model: 3
                    Rectangle {
                        required property int index
                        width: 260 - index * 30
                        height: 10
                        radius: 5
                        anchors.horizontalCenter: parent.horizontalCenter
                        color: theme.surfaceAlt
                        SequentialAnimation on opacity {
                            loops: Animation.Infinite
                            NumberAnimation { from: 0.35; to: 1.0; duration: 620; easing.type: Easing.InOutSine }
                            NumberAnimation { from: 1.0; to: 0.35; duration: 620; easing.type: Easing.InOutSine }
                        }
                    }
                }
            }
        }
    }

    // ============================================================ 模组详情
    Rectangle {
        id: detailLayer
        objectName: "modDetailLayer"
        anchors.fill: parent
        z: 50
        visible: page.detailOpen
        color: theme.bg

        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: 26
            anchors.rightMargin: 22
            anchors.topMargin: 4
            anchors.bottomMargin: 8
            spacing: 10

            // ------------------------------------------------ 顶部操作条
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                SproutButton {
                    text: "← 返回"
                    primary: false
                    implicitHeight: 32
                    fontSize: 12
                    onClicked: bridge.closeModDetail()
                }

                Text {
                    Layout.fillWidth: true
                    text: bridge.modDetail.title || ""
                    font.pixelSize: 16
                    font.weight: Font.DemiBold
                    color: theme.text1
                    elide: Text.ElideRight
                }

                Text {
                    text: bridge.modDetailLoading ? "加载中…" : (bridge.detailVersionCount + " 个版本文件")
                    font.pixelSize: 11
                    color: theme.text3
                }

                SproutButton {
                    readonly property bool isCf: (bridge.modDetail.source || bridge.modSource) === "curseforge"
                    text: isCf ? "转到 CurseForge" : "转到 Modrinth"
                    primary: false
                    implicitHeight: 32
                    fontSize: 12
                    active: (bridge.modDetail.sourceUrl || "").length > 0
                    onClicked: bridge.openUrl(bridge.modDetail.sourceUrl || "")
                }
            }

            // ------------------------------------------------ 头部卡片
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 112
                radius: 14
                color: theme.card
                border.width: 1
                border.color: theme.border

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 14

                    Rectangle {
                        Layout.preferredWidth: 76
                        Layout.preferredHeight: 76
                        radius: 12
                        color: theme.surfaceAlt

                        Image {
                            anchors.fill: parent
                            anchors.margins: 8
                            source: bridge.modDetail.iconUrl || ""
                            fillMode: Image.PreserveAspectFit
                            asynchronous: true
                        }
                    }

                    Column {
                        Layout.fillWidth: true
                        spacing: 5

                        Text {
                            text: bridge.modDetail.title || ""
                            font.pixelSize: 18
                            font.weight: Font.DemiBold
                            color: theme.text1
                        }

                        Text {
                            width: parent.width
                            text: bridge.modDetail.description || ""
                            font.pixelSize: 12
                            color: theme.text2
                            wrapMode: Text.WordWrap
                            maximumLineCount: 2
                            elide: Text.ElideRight
                        }

                        Text {
                            width: parent.width
                            text: "下载 " + page.fmtCount(bridge.modDetail.downloads)
                                  + "  ·  更新 " + (bridge.modDetail.updated || "")
                                  + "  ·  " + ((bridge.modDetail.loaders || []).join(" / ") || "通用")
                                  + "  ·  分类 " + ((bridge.modDetail.categories || []).slice(0, 3).join(" / ") || "无")
                            font.pixelSize: 11
                            color: theme.text3
                            elide: Text.ElideRight
                        }
                    }
                }
            }

            // ------------------------------------------------ 下载操作行
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                visible: bridge.detailVersionCount > 0

                Text {
                    text: "当前版本 " + page.activeVersion
                    font.pixelSize: 11
                    color: theme.text3
                }

                Item { Layout.fillWidth: true }

                SproutButton {
                    text: "下载此版本"
                    primary: true
                    active: page.activeVersion.length > 0 && !bridge.busy
                    implicitHeight: 38
                    fontSize: 13
                    onClicked: page.downloadVersion(page.activeVersion)
                }

                SproutButton {
                    text: "▾"
                    primary: false
                    implicitHeight: 38
                    implicitWidth: 40
                    fontSize: 13
                    active: bridge.detailVersionCount > 0
                    onClicked: versionPicker.open()
                }
            }

            // ------------------------------------------------ 游戏版本标签（列出全部支持版本）
            Flickable {
                id: versionFlick
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(verFlow.height, 70)
                contentWidth: width
                contentHeight: verFlow.height
                clip: true
                visible: (bridge.modDetail.gameVersions || []).length > 0
                boundsBehavior: Flickable.StopAtBounds

                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                Flow {
                    id: verFlow
                    width: versionFlick.width
                    spacing: 6

                    SproutButton {
                        text: "全部"
                        primary: bridge.detailFilter === ""
                        implicitHeight: 28
                        fontSize: 11
                        onClicked: bridge.setDetailVersionFilter("")
                    }

                    Repeater {
                        model: bridge.modDetail.gameVersions || []

                        SproutButton {
                            required property var modelData
                            text: modelData
                            primary: bridge.detailFilter === modelData
                            implicitHeight: 28
                            fontSize: 11
                            onClicked: bridge.setDetailVersionFilter(modelData)
                        }
                    }
                }
            }

            // ------------------------------------------------ 版本列表
            ListView {
                id: detailList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 6
                model: bridge.modVersionsModel
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                delegate: Rectangle {
                    id: verRow
                    required property var modelData
                    readonly property bool sel: page.activeVersion === modelData.id

                    width: ListView.view.width
                    height: 58
                    radius: 10
                    color: sel ? theme.accentSoft
                              : (verHover.containsMouse ? theme.surfaceAlt : theme.surface)
                    border.width: 1
                    border.color: sel ? theme.accent : theme.border
                    Behavior on color { ColorAnimation { duration: 140 } }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 12
                        spacing: 12

                        Column {
                            Layout.fillWidth: true
                            spacing: 3

                            Text {
                                text: (modelData.loader || "通用") + " · " + (modelData.gameVersions || "全版本")
                                font.pixelSize: 13
                                color: theme.text1
                                elide: Text.ElideRight
                                width: verRow.width - 190
                            }

                            Text {
                                text: modelData.versionNumber + "  ·  " + modelData.date
                                      + (modelData.fileName ? ("  ·  " + modelData.fileName) : "")
                                font.pixelSize: 10
                                color: theme.text3
                                elide: Text.ElideMiddle
                                width: verRow.width - 190
                            }
                        }

                        SproutButton {
                            text: "下载"
                            primary: true
                            active: !bridge.busy
                            implicitHeight: 30
                            fontSize: 12
                            onClicked: page.downloadVersion(modelData.id)
                        }

                        SproutButton {
                            text: "▾"
                            primary: false
                            implicitHeight: 30
                            implicitWidth: 32
                            fontSize: 12
                            onClicked: {
                                page.selectedVersion = modelData.id;
                                versionPicker.open();
                            }
                        }
                    }

                    MouseArea {
                        id: verHover
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.NoButton
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                visible: bridge.detailVersionCount === 0 && !bridge.modDetailLoading
                text: "该筛选下没有可用文件，换个游戏版本标签试试"
                font.pixelSize: 12
                color: theme.text3
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }

    // ============================================================ 版本选择器
    Popup {
        id: versionPicker
        objectName: "versionPicker"
        parent: Overlay.overlay
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        width: 560
        height: 480
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
                text: "选择要下载的版本"
                font.pixelSize: 13
                font.weight: Font.DemiBold
                color: theme.text1
            }

            ListView {
                id: pickerList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 4
                model: bridge.modVersionsModel
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                delegate: Rectangle {
                    id: pickRow
                    required property var modelData
                    width: ListView.view.width
                    height: 50
                    radius: 8
                    color: page.activeVersion === modelData.id ? theme.accentSoft
                                                                : (pickMouse.containsMouse ? theme.surfaceAlt : "transparent")

                    Column {
                        anchors.left: parent.left
                        anchors.leftMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2

                        Text {
                            text: (modelData.loader || "通用") + " · " + (modelData.gameVersions || "全版本")
                            font.pixelSize: 12
                            color: theme.text1
                            width: pickRow.width - 40
                            elide: Text.ElideRight
                        }

                        Text {
                            text: modelData.versionNumber + "  ·  " + modelData.date
                            font.pixelSize: 10
                            color: theme.text3
                            width: pickRow.width - 40
                            elide: Text.ElideRight
                        }
                    }

                    MouseArea {
                        id: pickMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            page.selectedVersion = modelData.id;
                            versionPicker.close();
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true

                Item { Layout.fillWidth: true }

                SproutButton {
                    text: "下载所选版本"
                    primary: true
                    active: page.activeVersion.length > 0 && !bridge.busy
                    implicitHeight: 36
                    fontSize: 13
                    onClicked: {
                        versionPicker.close();
                        page.downloadVersion(page.activeVersion);
                    }
                }
            }
        }
    }

    // ------------------------------------------------------ 模组加载器选择弹窗
    Popup {
        id: loaderPopup
        objectName: "loaderPopup"
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(460, page.width - 60)
        height: Math.min(600, Math.max(280, contentItem.implicitHeight + 36))
        modal: true
        dim: true
        focus: true
        padding: 18
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            radius: 14
            color: theme.card
            border.width: 1
            border.color: theme.border
        }

        contentItem: ColumnLayout {
            spacing: 10
            width: loaderPopup.availableWidth

            Text {
                Layout.fillWidth: true
                text: "该实例还没有安装模组加载器"
                font.pixelSize: 15
                font.bold: true
                color: theme.text1
            }

            Text {
                Layout.fillWidth: true
                text: "实例「" + bridge.loaderPromptInstance + "」（游戏版本 " + bridge.loaderPromptGame
                      + "）当前为原版，无法直接装载模组。请选择要安装的模组加载器，安装完成后会自动回到模组栏目并按该实例筛选。"
                font.pixelSize: 12
                color: theme.text3
                wrapMode: Text.WordWrap
            }

            Repeater {
                model: bridge.loaderPromptChoices

                SproutButton {
                    required property var modelData
                    Layout.fillWidth: true
                    text: modelData.label
                    primary: true
                    active: !bridge.busy
                    implicitHeight: 36
                    fontSize: 12
                    onClicked: bridge.installLoaderForInstance(modelData.key)
                }
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                SproutButton {
                    objectName: "loaderPromptCancel"
                    text: "暂不安装，仅浏览模组市场"
                    implicitHeight: 34
                    fontSize: 12
                    onClicked: bridge.closeLoaderPrompt()
                }

                Item { Layout.fillWidth: true }
            }
        }
    }

    // ---------------------------------------------------------- 前置模组确认弹窗
    Popup {
        id: depPopup
        objectName: "depPopup"
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(560, page.width - 60)
        height: Math.min(540, page.height - 60)
        modal: true
        dim: true
        focus: true
        padding: 0
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            radius: 14
            color: theme.card
            border.width: 1
            border.color: theme.border
        }

        contentItem: ColumnLayout {
            spacing: 10
            anchors.fill: parent
            anchors.margins: 18

            Text {
                Layout.fillWidth: true
                text: "缺少前置模组"
                font.pixelSize: 15
                font.bold: true
                color: theme.text1
            }

            Text {
                Layout.fillWidth: true
                text: bridge.depTitle
                font.pixelSize: 12
                color: theme.text2
                wrapMode: Text.WordWrap
            }

            Text {
                Layout.fillWidth: true
                text: bridge.depMessage
                font.pixelSize: 11
                color: theme.text3
                wrapMode: Text.WordWrap
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: theme.border
            }

            ListView {
                id: depList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 6
                model: bridge.depRows
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                delegate: Rectangle {
                    required property var modelData
                    width: depList.width
                    height: 52
                    radius: 9
                    color: theme.surfaceAlt

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 9
                        spacing: 9

                        Image {
                            Layout.preferredWidth: 32
                            Layout.preferredHeight: 32
                            source: modelData.iconUrl || ""
                            visible: (modelData.iconUrl || "").length > 0
                            fillMode: Image.PreserveAspectFit
                            asynchronous: true
                            sourceSize.width: 64
                            sourceSize.height: 64
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            Text {
                                Layout.fillWidth: true
                                text: modelData.title
                                font.pixelSize: 12
                                color: theme.text1
                                elide: Text.ElideRight
                            }

                            Text {
                                Layout.fillWidth: true
                                text: modelData.versionNumber + "  ·  " + page.fmtSize(modelData.size)
                                font.pixelSize: 10
                                color: theme.text3
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                text: "共 " + bridge.depCount + " 个前置 · 约 " + page.fmtSize(bridge.depTotalSize)
                font.pixelSize: 11
                color: theme.text3
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                SproutButton {
                    objectName: "depCancel"
                    text: "取消"
                    implicitHeight: 34
                    fontSize: 12
                    onClicked: bridge.cancelDepsDownload()
                }

                SproutButton {
                    objectName: "depOnlySelected"
                    text: "仅下载所选"
                    implicitHeight: 34
                    fontSize: 12
                    onClicked: bridge.downloadSelectedOnly()
                }

                Item { Layout.fillWidth: true }

                SproutButton {
                    objectName: "depDownloadAll"
                    text: "全部一并下载"
                    primary: true
                    active: true
                    implicitHeight: 34
                    fontSize: 12
                    onClicked: bridge.confirmDepsDownload()
                }
            }
        }
    }

    Connections {
        target: bridge
        function onLoaderPromptChanged() {
            if (bridge.loaderPromptOpen) {
                if (!loaderPopup.opened)
                    loaderPopup.open();
            } else if (loaderPopup.opened) {
                loaderPopup.close();
            }
        }

        function onModFilterChanged() {
            page.syncInstFilter();
            if (bridge.modFilterGame.length > 0)
                page.tab = 0;
        }

        function onDepChanged() {
            if (bridge.depOpen) {
                depPopup.open();
            } else {
                depPopup.close();
            }
        }
    }
}
