import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: page

    property string loginCode: ""
    property string loginUri: ""
    property string offlineName: ""
    property string skinTarget: ""
    property string skinName: ""
    property string skinModel: "classic"
    property string skinPreviewUrl: ""

    function openSkin(id, name) {
        page.skinTarget = String(id || "");
        page.skinName = String(name || "");
        page.skinModel = bridge.accountSkinModel(page.skinTarget);
        page.refreshPreview();
    }

    function closeSkin() {
        page.skinTarget = "";
        page.skinPreviewUrl = "";
    }

    function refreshPreview() {
        page.skinPreviewUrl = page.skinTarget.length > 0
                ? bridge.skinPreview(page.skinTarget) : "";
    }

    function initialOf(name) {
        var s = String(name || "");
        return s.length > 0 ? s.charAt(0).toUpperCase() : "?";
    }

    function shortUuid(u) {
        var s = String(u || "");
        return s.length > 8 ? s.substring(0, 8) : s;
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 26
        anchors.rightMargin: 22
        anchors.topMargin: 4
        anchors.bottomMargin: 8
        spacing: 12

        // ---------------------------------------------------- 当前账号
        Card {
            Layout.fillWidth: true
            Layout.preferredHeight: 118
            corner: 14
            interactive: false

            RowLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 16

                Rectangle {
                    Layout.preferredWidth: 58
                    Layout.preferredHeight: 58
                    radius: 29
                    color: theme.accentSoft

                    Text {
                        anchors.centerIn: parent
                        text: page.initialOf(bridge.activeAccount.name)
                        font.pixelSize: 24
                        font.weight: Font.DemiBold
                        color: theme.accent
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 5

                    Text {
                        text: bridge.activeAccount.name || "未登录"
                        font.pixelSize: 17
                        font.weight: Font.DemiBold
                        color: theme.text1
                    }

                    RowLayout {
                        spacing: 10

                        Rectangle {
                            Layout.preferredHeight: 20
                            Layout.preferredWidth: typeText.implicitWidth + 16
                            radius: 10
                            color: theme.surfaceAlt

                            Text {
                                id: typeText
                                anchors.centerIn: parent
                                text: bridge.activeAccount.label || "离线账户"
                                font.pixelSize: 10
                                color: theme.text3
                            }
                        }

                        Text {
                            text: "UUID " + page.shortUuid(bridge.activeAccount.uuid)
                            font.pixelSize: 11
                            color: theme.text3
                        }
                    }

                    Text {
                        text: "启动游戏时使用此账号登录，皮肤与披风跟随账号身份"
                        font.pixelSize: 11
                        color: theme.text3
                    }
                }

                SproutButton {
                    text: bridge.loginBusy ? "登录中…" : "微软账户登录"
                    primary: true
                    active: !bridge.loginBusy
                    implicitHeight: 36
                    fontSize: 12
                    onClicked: bridge.startMicrosoftLogin()
                }
            }
        }

        // ---------------------------------------------------- 登录进度 / 设备码
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 62 : 0
            visible: bridge.loginBusy || page.loginCode.length > 0
            radius: 12
            color: theme.surfaceAlt
            border.width: 1
            border.color: theme.border

            RowLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 14

                Text {
                    text: bridge.loginBusy ? "请在浏览器输入下列代码完成授权" : "上次授权码"
                    font.pixelSize: 12
                    color: theme.text2
                }

                Rectangle {
                    Layout.preferredHeight: 30
                    Layout.preferredWidth: codeText.implicitWidth + 22
                    radius: 8
                    color: theme.card

                    Text {
                        id: codeText
                        anchors.centerIn: parent
                        text: page.loginCode.length > 0 ? page.loginCode : "— — —"
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                        font.letterSpacing: 2
                        color: theme.accent
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (page.loginCode.length > 0)
                                bridge.openUrl("https://www.microsoft.com/link");
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                SproutButton {
                    text: "打开授权页"
                    primary: false
                    active: page.loginUri.length > 0
                    implicitHeight: 30
                    fontSize: 11
                    onClicked: bridge.openUrl(page.loginUri.length > 0
                                              ? page.loginUri
                                              : "https://www.microsoft.com/link")
                }
            }
        }

        // ---------------------------------------------------- 添加账号
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Rectangle {
                Layout.preferredWidth: 240
                Layout.preferredHeight: 36
                radius: 10
                color: theme.surfaceAlt
                border.width: 1
                border.color: nameField.activeFocus ? theme.accent : "transparent"

                Behavior on border.color { ColorAnimation { duration: 160 } }

                TextField {
                    id: nameField
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    background: Item {}
                    placeholderText: "离线账号昵称"
                    placeholderTextColor: theme.text3
                    color: theme.text1
                    font.pixelSize: 13
                    verticalAlignment: TextInput.AlignVCenter
                    onTextChanged: page.offlineName = text
                    onAccepted: {
                        if (text.trim().length > 0) {
                            bridge.addOfflineAccount(text.trim());
                            text = "";
                        }
                    }
                }
            }

            SproutButton {
                text: "添加离线账号"
                primary: true
                active: page.offlineName.trim().length > 0
                implicitHeight: 36
                fontSize: 12
                onClicked: {
                    bridge.addOfflineAccount(page.offlineName.trim());
                    nameField.text = "";
                    page.offlineName = "";
                }
            }

            Item { Layout.fillWidth: true }

            Text {
                text: "共 " + bridge.accounts.length + " 个账号"
                font.pixelSize: 11
                color: theme.text3
            }
        }

        // ---------------------------------------------------- 账号列表
        Text {
            text: "全部账号"
            font.pixelSize: 12
            font.weight: Font.DemiBold
            color: theme.text2
        }

        ListView {
            id: accountList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 8
            model: bridge.accounts
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                required property var modelData

                width: accountList.width
                height: 62
                radius: 12
                color: theme.card
                border.width: 1
                border.color: modelData.active ? theme.accent : theme.border

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    spacing: 12

                    Rectangle {
                        Layout.preferredWidth: 34
                        Layout.preferredHeight: 34
                        radius: 17
                        color: modelData.active ? theme.accentSoft : theme.surfaceAlt

                        Text {
                            anchors.centerIn: parent
                            text: page.initialOf(modelData.name)
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                            color: modelData.active ? theme.accent : theme.text2
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            text: modelData.name
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: theme.text1
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        Text {
                            text: modelData.label + " · " + page.shortUuid(modelData.uuid)
                                  + (modelData.expired ? " · 登录已过期" : "")
                            font.pixelSize: 10
                            color: modelData.expired ? "#D98A3A" : theme.text3
                        }
                    }

                    SproutButton {
                        text: modelData.active ? "当前使用" : "切换"
                        primary: false
                        active: !modelData.active
                        implicitHeight: 30
                        fontSize: 11
                        onClicked: bridge.setActiveAccount(modelData.id)
                    }

                    SproutButton {
                        text: "设置皮肤"
                        primary: false
                        active: modelData.type === "microsoft"
                        implicitHeight: 30
                        fontSize: 11
                        onClicked: page.openSkin(modelData.id, modelData.name)
                    }

                    SproutButton {
                        text: "移除"
                        primary: false
                        active: bridge.accounts.length > 1
                        implicitHeight: 30
                        fontSize: 11
                        onClicked: bridge.removeAccount(modelData.id)
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: accountList.count === 0
                text: "还没有账号，先添加一个离线账号"
                font.pixelSize: 12
                color: theme.text3
            }
        }
    }

    Connections {
        target: bridge
        function onDeviceCode(code, uri) {
            page.loginCode = code;
            page.loginUri = uri;
        }
        function onSkinChanged() {
            page.refreshPreview();
        }
    }

    // ---------------------------------------------------- 皮肤面板
    Item {
        anchors.fill: parent
        visible: page.skinTarget.length > 0
        z: 60

        Rectangle {
            anchors.fill: parent
            color: "#66000000"
            MouseArea {
                anchors.fill: parent
                onClicked: page.closeSkin()
            }
        }

        Rectangle {
            anchors.centerIn: parent
            width: Math.min(440, page.width - 40)
            height: 292
            radius: 16
            color: theme.card
            border.width: 1
            border.color: theme.border

            MouseArea { anchors.fill: parent }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Text {
                        text: "设置皮肤 · " + (page.skinName || "当前账号")
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                        color: theme.text2
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    SproutButton {
                        text: "关闭"
                        primary: false
                        implicitHeight: 28
                        fontSize: 11
                        onClicked: page.closeSkin()
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 16

                    Rectangle {
                        Layout.preferredWidth: 150
                        Layout.fillHeight: true
                        radius: 12
                        color: theme.surfaceAlt
                        border.width: 1
                        border.color: theme.border

                        Text {
                            anchors.centerIn: parent
                            visible: page.skinPreviewUrl.length === 0
                            text: "暂无预览"
                            font.pixelSize: 11
                            color: theme.text3
                        }

                        Image {
                            anchors.fill: parent
                            anchors.margins: 10
                            source: page.skinPreviewUrl
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                            cache: false
                            visible: page.skinPreviewUrl.length > 0
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 10

                        Text {
                            text: "手臂模型"
                            font.pixelSize: 11
                            color: theme.text3
                        }

                        RowLayout {
                            spacing: 8

                            SproutButton {
                                text: "经典 4px"
                                primary: page.skinModel !== "slim"
                                implicitHeight: 30
                                fontSize: 11
                                onClicked: page.skinModel = "classic"
                            }

                            SproutButton {
                                text: "纤细 3px"
                                primary: page.skinModel === "slim"
                                implicitHeight: 30
                                fontSize: 11
                                onClicked: page.skinModel = "slim"
                            }
                        }

                        Text {
                            text: "支持 64x64、64x32 或整倍数高清 PNG，单文件不超过 8MB"
                            font.pixelSize: 10
                            color: theme.text3
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Item { Layout.fillHeight: true }

                        SproutButton {
                            text: "从官方同步"
                            primary: false
                            active: !bridge.skinBusy
                            implicitHeight: 32
                            fontSize: 11
                            Layout.fillWidth: true
                            onClicked: bridge.refreshAccountSkin(page.skinTarget)
                        }
                    }
                }

                SproutButton {
                    text: bridge.skinBusy ? "上传中…" : "选择 PNG 并上传"
                    primary: true
                    active: !bridge.skinBusy
                    implicitHeight: 36
                    fontSize: 12
                    Layout.fillWidth: true
                    onClicked: {
                        var p = bridge.pickFile("选择皮肤图片", "皮肤图片 (*.png)");
                        if (p && p.length > 0)
                            bridge.setAccountSkin(page.skinTarget, p, page.skinModel);
                    }
                }
            }
        }
    }
}
