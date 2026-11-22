import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: page

    function levelColor(level) {
        if (level === "ok")
            return theme.accent;
        if (level === "warn")
            return "#D99A3A";
        if (level === "error")
            return "#E05555";
        return theme.text3;
    }

    function levelGlyph(level) {
        if (level === "ok")
            return "✓";
        if (level === "warn")
            return "!";
        if (level === "error")
            return "✕";
        return "·";
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 26
        anchors.rightMargin: 22
        anchors.topMargin: 4
        anchors.bottomMargin: 8
        spacing: 12

        // ------------------------------------------------- 操作条
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            SproutButton {
                text: bridge.diagnosing ? "诊断中…" : "开始自检"
                primary: true
                active: !bridge.diagnosing
                implicitHeight: 36
                fontSize: 13
                onClicked: bridge.runDiagnose()
            }

            SproutButton {
                text: "打开日志目录"
                primary: false
                active: true
                implicitHeight: 36
                fontSize: 12
                onClicked: bridge.openPath(bridge.logsPath())
            }

            SproutButton {
                text: "打开报告"
                primary: false
                active: bridge.diagnoseReportPath.length > 0
                implicitHeight: 36
                fontSize: 12
                onClicked: bridge.openPath(bridge.diagnoseReportPath)
            }

            Item { Layout.fillWidth: true }

            Text {
                text: "检查项 " + bridge.diagnoseItems.length + " 项"
                font.pixelSize: 11
                color: theme.text3
            }
        }

        // ------------------------------------------------- 结论
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 56
            radius: 12
            color: theme.surfaceAlt
            border.width: 1
            border.color: theme.border

            RowLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 12

                Rectangle {
                    Layout.preferredWidth: 8
                    Layout.preferredHeight: 8
                    radius: 4
                    color: theme.accent
                    visible: bridge.diagnoseSummary.length > 0
                }

                Text {
                    Layout.fillWidth: true
                    text: bridge.diagnoseSummary.length > 0
                          ? bridge.diagnoseSummary
                          : "点击「开始自检」检查游戏目录、Java、版本清单与网络连通性"
                    font.pixelSize: 13
                    font.weight: bridge.diagnoseSummary.length > 0 ? Font.DemiBold : Font.Normal
                    color: theme.text1
                    elide: Text.ElideRight
                }

                Text {
                    text: bridge.diagnoseReportPath.length > 0 ? "报告已保存" : ""
                    font.pixelSize: 11
                    color: theme.text3
                }
            }
        }

        // ------------------------------------------------- 明细
        ListView {
            id: diagList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 8
            model: bridge.diagnoseItems
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                required property var modelData

                width: diagList.width
                height: detailText.implicitHeight + 46
                radius: 12
                color: theme.card
                border.width: 1
                border.color: theme.border

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 12

                    Rectangle {
                        Layout.preferredWidth: 26
                        Layout.preferredHeight: 26
                        Layout.alignment: Qt.AlignTop
                        radius: 13
                        color: Qt.rgba(page.levelColor(modelData.level).r,
                                       page.levelColor(modelData.level).g,
                                       page.levelColor(modelData.level).b, 0.16)

                        Text {
                            anchors.centerIn: parent
                            text: page.levelGlyph(modelData.level)
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: page.levelColor(modelData.level)
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Text {
                                text: modelData.title
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                color: theme.text1
                            }

                            Rectangle {
                                Layout.preferredHeight: 18
                                Layout.preferredWidth: badgeText.implicitWidth + 14
                                radius: 9
                                color: Qt.rgba(page.levelColor(modelData.level).r,
                                               page.levelColor(modelData.level).g,
                                               page.levelColor(modelData.level).b, 0.14)

                                Text {
                                    id: badgeText
                                    anchors.centerIn: parent
                                    text: modelData.label
                                    font.pixelSize: 10
                                    color: page.levelColor(modelData.level)
                                }
                            }

                            Item { Layout.fillWidth: true }
                        }

                        Text {
                            id: detailText
                            Layout.fillWidth: true
                            text: modelData.detail + (modelData.action && modelData.action.length > 0
                                                     ? "\n建议：" + modelData.action : "")
                            font.pixelSize: 11
                            color: theme.text3
                            wrapMode: Text.WordWrap
                            lineHeight: 1.3
                        }
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: diagList.count === 0 && !bridge.diagnosing
                text: "暂无诊断结果"
                font.pixelSize: 12
                color: theme.text3
            }
        }
    }
}
