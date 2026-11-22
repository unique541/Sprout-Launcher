import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// 自动更新弹窗：发现新版本 -> 下载安装包 -> 提示安装（安装程序启动后启动器退出）
Item {
    id: dlg

    anchors.fill: parent
    visible: bridge.updatePromptVisible
    z: 950

    readonly property string stage: bridge.updateStage
    readonly property var info: bridge.updateInfo
    readonly property string newVer: (info && info.version) ? String(info.version) : ""
    readonly property string curVer: (info && info.current) ? String(info.current) : bridge.appVersion

    function titleText() {
        if (stage === "downloading")
            return "正在下载更新包";
        if (stage === "ready")
            return "更新包已下载完成";
        if (stage === "installing")
            return "正在启动安装程序";
        if (stage === "error")
            return "更新未完成";
        return "发现新版本 " + newVer;
    }

    function verText() {
        if (stage === "available")
            return "当前版本 " + curVer + "    →    最新版本 " + newVer;
        if (stage === "ready" || stage === "installing")
            return "新版本 " + newVer + " 已下载";
        return "当前版本 " + curVer;
    }

    function summaryText() {
        if (stage === "available")
            return dlg.info && dlg.info.asset_name
                   ? ("安装包：" + dlg.info.asset_name + (dlg.info.published ? ("　发布 " + dlg.info.published) : ""))
                   : "将下载该版本安装包";
        if (stage === "downloading")
            return bridge.updateMessage;
        if (stage === "ready")
            return bridge.updateMessage;
        if (stage === "installing")
            return "安装程序已打开，启动器即将退出，请在安装向导里完成安装。安装结束后安装包会自动删除。";
        if (stage === "error")
            return bridge.updateMessage;
        return "";
    }

    // 吞掉遮罩上的点击，避免误触到下层界面
    MouseArea {
        anchors.fill: parent
        onClicked: {}
    }

    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.52
    }

    Rectangle {
        id: card

        anchors.centerIn: parent
        width: 580
        height: body.implicitHeight + 44
        radius: 18
        color: theme.card
        border.width: 1
        border.color: dlg.stage === "error" ? theme.border : theme.accent

        ColumnLayout {
            id: body

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 22
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Rectangle {
                    Layout.preferredWidth: 40
                    Layout.preferredHeight: 40
                    radius: 12
                    color: theme.accentSoft

                    Text {
                        anchors.centerIn: parent
                        text: dlg.stage === "available" ? "↑" : (dlg.stage === "error" ? "!" : "⏵")
                        font.pixelSize: 18
                        font.weight: Font.DemiBold
                        color: theme.accent
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    Text {
                        Layout.fillWidth: true
                        text: dlg.titleText()
                        font.pixelSize: 16
                        font.weight: Font.DemiBold
                        color: theme.text1
                        elide: Text.ElideRight
                    }

                    Text {
                        Layout.fillWidth: true
                        text: dlg.verText()
                        font.pixelSize: 11
                        color: theme.text3
                        elide: Text.ElideRight
                    }
                }

                SproutButton {
                    text: "关于页"
                    primary: false
                    active: dlg.stage !== "installing"
                    visible: dlg.stage !== "installing"
                    implicitHeight: 30
                    fontSize: 11
                    onClicked: bridge.openUrl(dlg.info && dlg.info.page ? dlg.info.page : "https://github.com/" + bridge.updateRepo)
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: theme.border
                visible: dlg.stage !== "installing"
            }

            // 更新说明
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 168
                radius: 12
                color: theme.surfaceAlt
                visible: dlg.stage === "available" || dlg.stage === "downloading" || dlg.stage === "ready"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    Text {
                        text: "本次更新内容"
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        color: theme.text1
                    }

                    Flickable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        contentWidth: width
                        contentHeight: notesText.implicitHeight
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        Text {
                            id: notesText

                            width: parent.width
                            text: bridge.updateNotesText
                            font.pixelSize: 11
                            lineHeight: 1.35
                            color: theme.text3
                            wrapMode: Text.WordWrap
                            textFormat: Text.PlainText
                        }
                    }
                }
            }

            // 下载进度
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6
                visible: dlg.stage === "downloading"

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 8
                    radius: 4
                    color: theme.surfaceAlt

                    Rectangle {
                        width: parent.width * Math.max(0, Math.min(1, bridge.updateProgress))
                        height: parent.height
                        radius: 4
                        color: theme.accent

                        Behavior on width { NumberAnimation { duration: 120 } }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: Math.round(bridge.updateProgress * 100) + "%"
                    horizontalAlignment: Text.AlignRight
                    font.pixelSize: 10
                    color: theme.text3
                }
            }

            Text {
                Layout.fillWidth: true
                text: dlg.summaryText()
                visible: text.length > 0
                font.pixelSize: 11
                color: dlg.stage === "error" ? theme.accent : theme.text3
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                visible: dlg.stage !== "installing"

                SproutButton {
                    text: "跳过此版本"
                    primary: false
                    active: dlg.stage === "available"
                    visible: dlg.stage === "available"
                    implicitHeight: 34
                    fontSize: 12
                    onClicked: bridge.skipUpdateVersion()
                }

                SproutButton {
                    text: "稍后再说"
                    primary: false
                    active: dlg.stage === "available" || dlg.stage === "error"
                    visible: dlg.stage === "available" || dlg.stage === "error"
                    implicitHeight: 34
                    fontSize: 12
                    onClicked: bridge.dismissUpdate()
                }

                SproutButton {
                    text: "打开下载目录"
                    primary: false
                    active: dlg.stage === "ready"
                    visible: dlg.stage === "ready"
                    implicitHeight: 34
                    fontSize: 12
                    onClicked: bridge.openUpdateDownloads()
                }

                Item { Layout.fillWidth: true }

                SproutButton {
                    text: dlg.stage === "ready" ? "稍后安装" : "关闭"
                    primary: false
                    active: dlg.stage === "ready"
                    visible: dlg.stage === "ready"
                    implicitHeight: 34
                    fontSize: 12
                    onClicked: bridge.dismissUpdate()
                }

                SproutButton {
                    text: dlg.stage === "error" ? "重新下载" : "立即更新"
                    primary: true
                    active: dlg.stage === "available" || dlg.stage === "error"
                    visible: dlg.stage === "available" || dlg.stage === "error"
                    implicitHeight: 34
                    fontSize: 12
                    onClicked: bridge.downloadUpdate()
                }

                SproutButton {
                    text: "立即安装"
                    primary: true
                    active: dlg.stage === "ready"
                    visible: dlg.stage === "ready"
                    implicitHeight: 34
                    fontSize: 12
                    onClicked: bridge.installUpdate()
                }
            }
        }
    }
}
