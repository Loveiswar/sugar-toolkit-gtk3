# Copyright (C) 2006, Red Hat, Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import os
import logging

import dbus
import dbus.service
import gtk
import gobject
import datetime

from sugar.presence import PresenceService
from sugar.datastore import datastore
from sugar import activity
from sugar import env
import sugar.util

ACTIVITY_SERVICE_NAME = "org.laptop.Activity"
ACTIVITY_SERVICE_PATH = "/org/laptop/Activity"
ACTIVITY_INTERFACE = "org.laptop.Activity"

from sugar.graphics.grid import Grid

settings = gtk.settings_get_default()

grid = Grid()
sizes = 'gtk-large-toolbar=%d, %d' % (grid.dimension(1), grid.dimension(1))
settings.set_string_property('gtk-icon-sizes', sizes, '')

def get_service_name(xid):
    return ACTIVITY_SERVICE_NAME + '%d' % xid

def get_object_path(xid):
    return ACTIVITY_SERVICE_PATH + "/%s" % xid 

def get_service(xid):
    bus = dbus.SessionBus()
    proxy_obj = bus.get_object(get_service_name(xid), get_object_path(xid))
    return dbus.Interface(proxy_obj, ACTIVITY_INTERFACE)


class ActivityDbusService(dbus.service.Object):
    """Base dbus service object that each Activity uses to export dbus methods.
    
    The dbus service is separate from the actual Activity object so that we can
    tightly control what stuff passes through the dbus python bindings."""

    def __init__(self, activity):
        xid = activity.window.xid
        bus = dbus.SessionBus()
        bus_name = dbus.service.BusName(get_service_name(xid), bus=bus)
        dbus.service.Object.__init__(self, bus_name, get_object_path(xid))

        self._activity = activity
        self._pservice = PresenceService.get_instance()       

    @dbus.service.method(ACTIVITY_INTERFACE)
    def start(self, activity_id):
        """Start the activity in unshared mode."""
        self._activity.start(activity_id)

    @dbus.service.method(ACTIVITY_INTERFACE)
    def join(self, activity_ps_path):
        """Join the activity specified by its presence service path."""
        activity_ps = self._pservice.get(activity_ps_path)
        return self._activity.join(activity_ps)

    @dbus.service.method(ACTIVITY_INTERFACE)
    def share(self):
        """Called by the shell to request the activity to share itself on the network."""
        self._activity.share()

    @dbus.service.method(ACTIVITY_INTERFACE)
    def get_id(self):
        """Get the activity identifier"""
        return self._activity.get_id()

    @dbus.service.method(ACTIVITY_INTERFACE)
    def get_type(self):
        """Get the activity type"""
        return self._activity.get_type()

    @dbus.service.method(ACTIVITY_INTERFACE)
    def get_shared(self):
        """Returns True if the activity is shared on the mesh."""
        return self._activity.get_shared()

    @dbus.service.method(ACTIVITY_INTERFACE,
                         in_signature="sas", out_signature="b")
    def execute(self, command, args):
        return self._activity.execute(command, args)

class Activity(gtk.Window):
    """Base Activity class that all other Activities derive from."""

    def __init__(self):
        gtk.Window.__init__(self)

        self.connect('destroy', self._destroy_cb)
        #self.connect('notify::title', self._title_changed_cb)

        self._shared = False
        self._activity_id = None
        self._service = None
        #self._journal_object = None
        self._pservice = PresenceService.get_instance()

        self.realize()
    
        group = gtk.Window()
        group.realize()
        self.window.set_group(group.window)

        self._bus = ActivityDbusService(self)

    def start(self, activity_id):
        """Start the activity."""
        if self._activity_id != None:
            logging.warning('The activity has been already started.')
            return

        self._activity_id = activity_id

        #ds = datastore.get_instance()
        #self._journal_object = ds.create('', {}, self._activity_id)
        #
        #date = datetime.datetime.now()
        #self._journal_jobject.set_properties({'date' : date,
        #                                      'title' : self.get_title()})

        self.present()

#    def get_journal_object(self):
#        """Returns the journal object associated with the activity."""
#        return self._journal_object

    def get_type(self):
        """Gets the activity type."""
        return env.get_bundle_service_name()

    def get_default_type(self):
        """Gets the type of the default activity network service"""
        return env.get_bundle_default_type()

    def get_shared(self):
        """Returns TRUE if the activity is shared on the mesh."""
        return self._shared

    def get_id(self):
        """Get the unique activity identifier."""
        return self._activity_id

    def join(self, activity_ps):
        """Join an activity shared on the network."""
        if self._activity_id != None:
            logging.warning('The activity has been already started.')
            return
        self._activity_id = activity_ps.get_id()

        self._shared = True

        # Publish the default service, it's a copy of
        # one of those we found on the network.
        default_type = self.get_default_type()
        services = activity_ps.get_services_of_type(default_type)
        if len(services) > 0:
            service = services[0]
            addr = service.get_address()
            port = service.get_port()
            properties = service.get_published_values()
            self._service = self._pservice.share_activity(
                            self, default_type, properties, addr, port)
        else:
            logging.error('Cannot join the activity')

        #ds = datastore.get_instance()
        #self._journal_object = ds.get_activity_object(self._activity_id)

        self.present()

    def share(self):
        """Share the activity on the network."""
        logging.debug('Share activity %s on the network.' % self.get_id())

        default_type = self.get_default_type()
        self._service = self._pservice.share_activity(self, default_type)
        self._shared = True

    def execute(self, command, args):
        """Execute the given command with args"""
        return False

    def _destroy_cb(self, window):
        if self._bus:
            del self._bus
            self._bus = None
        if self._service:
            self._pservice.unregister_service(self._service)

    def _title_changed_cb(self, window, spec):
	pass
#        jobject = self.get_journal_object()
#        if jobject:
#            jobject.set_properties({'title' : self.props.title})
