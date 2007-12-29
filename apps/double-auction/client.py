# Copyright 2007 Martin Geisler
#
# This file is part of VIFF, the Virtual Ideal Functionality Framework.
#
# VIFF is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# VIFF is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with VIFF in the file COPYING; if not, write to the Free
# Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA

from twisted.internet import gtk2reactor
gtk2reactor.install()
from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory, ServerFactory, Protocol


import pygtk
pygtk.require('2.0')
import gtk
import gtk.glade

from configobj import ConfigObj






PRICES = 10
TRADE_MAX = 100

class Client:

    def quit(self, *args):
        gtk.main_quit()

    def scale_changed(self, range):
        if not self.enforce_monotonic_scales:
            return
        value = range.get_value()
        index = self.scales.index(range)

        if self.widget_tree.get_widget("buyer").get_active():
            for scale in self.scales[:index]:
                if scale.get_value() < value:
                    scale.set_value(value)
            for scale in self.scales[index+1:]:
                if scale.get_value() > value:
                    scale.set_value(value)

        else:
            for scale in self.scales[:index]:
                if scale.get_value() > value:
                    scale.set_value(value)
            for scale in self.scales[index+1:]:
                if scale.get_value() < value:
                    scale.set_value(value)

    def buyer_toggled(self, widget):
        self.enforce_monotonic_scales = False
        for scale in self.scales:
            scale.set_value(TRADE_MAX - scale.get_value())
        self.enforce_monotonic_scales = True

    def save(self, event):
        auction_id = self.widget_tree.get_widget("auction_id").get_text()
        client_id = self.widget_tree.get_widget("client_id").get_text()
        if auction_id == "" or client_id == "":
            print "Must specify both Auction ID and Client ID"
            return

        filename = "auction-%s-client-%s.bids" % (auction_id, client_id)
        chooser = gtk.FileChooserDialog(title="Save bids as...",
                                        action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                        buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                                 gtk.STOCK_SAVE, gtk.RESPONSE_OK))
        chooser.set_current_name(filename)

        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            config = ConfigObj()
            config['auction_id'] = auction_id
            config['client_id'] = client_id

            buyer = self.widget_tree.get_widget("buyer").get_active()
            if buyer:
                config['client_type'] = 'buyer'
            else:
                config['client_type'] = 'seller'

            config['bids'] = {}
        
            for price, scale in zip(range(PRICES), self.scales):
                config['bids'][str(price)] = int(scale.get_value())
            
            config.filename = chooser.get_filename()
            config.write()
        chooser.destroy()

    def load(self, event):
        chooser = gtk.FileChooserDialog(title="Load bids from...",
                                        action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                        buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                                 gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        filter = gtk.FileFilter()
        filter.set_name("Auction bids")
        filter.add_pattern("*.bids")
        chooser.add_filter(filter)

        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            config = ConfigObj(chooser.get_filename())

            b = config['client_type'] == 'seller'
            self.widget_tree.get_widget("buyer").set_active(b)
            self.widget_tree.get_widget("seller").set_active(not b)

            self.enforce_monotonic_scales = False
            for price, scale in zip(range(PRICES), self.scales):
                scale.set_value(int(config['bids'][str(price)]))
            self.enforce_monotonic_scales = True
        chooser.destroy()

    def connect(self, event):
        print "connect"

    def __init__(self):

        ui = "auction-client.glade"
        self.widget_tree = gtk.glade.XML(ui, "window")

        signals = {"on_quit_clicked": self.quit,
                   "on_save_clicked": self.save,
                   "on_load_clicked": self.load,
                   "on_connect_clicked": self.connect,
                   "on_buyer_toggled": self.buyer_toggled}
        self.widget_tree.signal_autoconnect(signals)

        hbox = self.widget_tree.get_widget("scales")
        self.scales = []
        for price in range(PRICES):
            scale = gtk.VScale(gtk.Adjustment(TRADE_MAX//2, 0, TRADE_MAX,
                                              1, TRADE_MAX//10))
            scale.set_draw_value(True)
            scale.set_value_pos(gtk.POS_BOTTOM)
            scale.set_inverted(True)
            scale.set_digits(0)
            scale.connect('value-changed', self.scale_changed)

            self.scales.append(scale)
            hbox.add(scale)
        hbox.show_all()

        # Used when changing the scales en-mass
        self.enforce_monotonic_scales = True


if __name__ == "__main__":
    c = Client()
    reactor.run()
