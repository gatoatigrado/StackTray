from __future__ import print_function

from PyQt4.QtGui import *
from PyQt4.QtCore import *

import stackexchange
so = stackexchange.Site(stackexchange.StackOverflow, cache=0)

import urllib2
import os
import webbrowser
import time
import datetime
import math

import settings

class SystemTray(QSystemTrayIcon):

    """ Creates our System Tray icon and calls our worker to get new data """

    def __init__(self, icon, parent=None):
        QSystemTrayIcon.__init__(self, icon, parent)
        self.setToolTip("Text")

        menu = QMenu(parent)
        updateAction = menu.addAction("Update")
        exitAction = menu.addAction("Quit")
        QObject.connect(updateAction, SIGNAL("triggered()"), self.update)
        QObject.connect(exitAction, SIGNAL("triggered()"), qApp, SLOT("quit()"))

        self.setContextMenu(menu)

        # delta in hours
        self.delta = 24
        self.rep = None
        self.badges = None

        self.oldrep = None
        self.oldanswers = None
        self.id = settings.id

        self.refresh = settings.refresh * 1000 * 60

        self.show()
        self.update()

        self.timer = QTimer()
        QObject.connect(self.timer, SIGNAL("timeout()"), self.fetch)
        self.timer.start(self.refresh)
        self.connect(self, SIGNAL("messageClicked()"), self.goto_site)

    def fetch(self, manual=False):
        """ Fetch the latest data """

        print("fetch method")
        self.thread = Worker()
        self.connect(self.thread, SIGNAL("data"), self.run)
        self.thread.getData(settings, {"manual": manual})

    def update(self):
        """ Manually update"""

        self.fetch(manual=True)

    def run(self, data):
        """ The real "work" """
        print("update / run method")

        err = data.get("error")
        try: rep = data["reputation"]
        except KeyError: rep = -1
        try: questions = data["questions"]
        except KeyError: questions = []

        if err:
            print("error updating")
            err_msg = "ERROR UPDATING\n" + str(err)
            self.setToolTip(err_msg)
            if data["manual"]:
                self.showMessage("StackTray Message", err_msg, msecs=3000)
            return

        def abbrev(string):
            if len(string) < 50: return string
            return string[:50] + "..."

        def nanswers(v):
            if v == 0: return "NO ANSWERS"
            elif v == 1: return "1 answer"
            else: return "%d answers" %(v)

        q_summaries = []
        for q in questions:
            q_summaries.append("+%d, %s -- %s"
                %(q.score, nanswers(len(q.answers)), abbrev(q.title)))
        q_summary = "\n".join(q_summaries)

        alerts = []
        if self.oldrep != rep:
            alerts.append("You have %s reputation!" % rep)
        if self.oldanswers != q_summary:
            changes = "".join(map(lambda a: "\n    " + a, q_summaries))
            alerts.append("Changes to your last 3 questions:" + changes)

        self.oldrep = rep
        self.oldanswers = q_summary

        if (alerts):
            message = self.showMessage("StackTray Message",
                "\n".join(alerts), msecs=4000)
        elif data["manual"]:
            self.showMessage("StackTray Message",
                "No updates", msecs=600)
        else:
            print("reputation: ", rep)
            print("question summaries: ", q_summary)
        self.setToolTip(q_summary)

    def goto_site(self):
        """ Open in browser """

        webbrowser.open_new_tab("http://stackoverflow.com/users/%d" % self.id)

class Worker(QThread):
    """ Our worker thread """
    def __init__(self, parent=None):
        QThread.__init__(self, parent)

    def __del__(self):
        self.exiting = True
        self.wait()

    def getData(self, settings, data):
        self.settings = settings
        self.data = data
        self.start()

    def run(self):
        try:
            user = so.user(self.settings.id)
            user.fetch()
            questions = user.questions.fetch()[:3]
            for q in questions:
                q.fetch()
            self.data.update({"reputation": int(user.reputation),
                         "questions": questions })
            self.emit(SIGNAL("data"), self.data)
        except urllib2.HTTPError, e:
            self.data.update({ "error": e })
            self.emit(SIGNAL("data"), self.data)

