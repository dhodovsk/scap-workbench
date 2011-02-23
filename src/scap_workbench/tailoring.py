# -*- coding: utf-8 -*-
#
# Copyright 2010 Red Hat Inc., Durham, North Carolina.
# All Rights Reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
#      Maros Barabas        <mbarabas@redhat.com>
#      Vladimir Oberreiter  <xoberr01@stud.fit.vutbr.cz>

import pygtk
import gtk
import gobject
import pango

import abstract
import logging
import core
from events import EventObject

    
import commands
import filter
import render

from htmltextview import HtmlTextView
from threads import thread as threadSave

logger = logging.getLogger("scap-workbench")

class ItemList(abstract.List):
    
    def __init__(self, widget, core, progress=None, filter=None):
        self.core = core
        self.filter = filter
        self.old_selected = None
        self.data_model = commands.DHItemsTree("gui:tailoring:DHItemsTree", core, progress)
        abstract.List.__init__(self, "gui:tailoring:item_list", core, widget)
        self.get_TreeView().set_enable_tree_lines(True)
        self.model_changed = False
        
        selection = self.get_TreeView().get_selection()
        selection.set_mode(gtk.SELECTION_SINGLE)

        # actions
        self.add_receiver("gui:btn:menu:tailoring", "update", self.__update)
        self.add_receiver("gui:btn:tailoring:filter", "search", self.__search)
        self.add_receiver("gui:btn:tailoring:filter", "filter_add", self.__filter_add)
        self.add_receiver("gui:btn:tailoring:filter", "filter_del", self.__filter_del)
        self.add_receiver("gui:tailoring:DHItemsTree", "filled", self.__filter_refresh)
        self.add_receiver("edit:dialog_window:add_item", "add", self.__model_changed)
        
        selection.connect("changed", self.__cb_item_changed, self.get_TreeView())
        self.add_sender(self.id, "item_changed")

        self.init_filters(self.filter, self.data_model.model, self.data_model.new_model())

    def __update(self):

        if self.core.xccdf_file == None: self.data_model.model.clear()
        if "profile" not in self.__dict__ or self.profile != self.core.selected_profile or self.core.force_reload_items:
            if self.model_changed == True:
                md = gtk.MessageDialog(self.window, 
                        gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION,
                        gtk.BUTTONS_YES_NO, "Some items were added or deleted. \n Do you want update profile? ")
                md.set_title("Data changed")
                result = md.run()
                md.destroy()
                if result == gtk.RESPONSE_NO:
                    return
                
            self.model_changed == False
            self.profile = self.core.selected_profile
            self.get_TreeView().set_model(self.data_model.model)
            self.data_model.fill()
            self.core.force_reload_items = False

        if self.old_selected != self.core.selected_item:
            # Select the last one selected if there is one
            self.get_TreeView().get_model().foreach(self.set_selected, (self.core.selected_item, self.get_TreeView()))
            self.old_selected = self.core.selected_item

    def __search(self):
        self.search(self.filter.get_search_text(),1)
        
    def __filter_add(self):
        self.data_model.map_filter = self.filter_add(self.filter.filters)
        self.get_TreeView().get_model().foreach(self.set_selected, (self.core.selected_item, self.get_TreeView()))

    def __filter_del(self):
        self.data_model.map_filter = self.filter_del(self.filter.filters)
        self.get_TreeView().get_model().foreach(self.set_selected, (self.core.selected_item, self.get_TreeView()))

    def __filter_refresh(self):
        self.data_model.map_filter = self.filter_del(self.filter.filters)
        self.get_TreeView().get_model().foreach(self.set_selected, (self.core.selected_item, self.get_TreeView()))

    def __model_changed(self):
        self.model_changed = True

        
    @threadSave
    def __cb_item_changed(self, widget, treeView):
        """Make all changes in application in separate threads: workaround for annoying
        blinking when redrawing treeView
        TODO: Make this with idle function, not with new thread
        """

        gtk.gdk.threads_enter()
        selection = treeView.get_selection( )
        if selection != None: 
            (model, iter) = selection.get_selected( )
            if iter: 
                self.core.selected_item = model.get_value(iter, commands.DHItemsTree.COLUMN_ID)
                self.emit("update")
        treeView.columns_autosize()
        gtk.gdk.threads_leave()


class ValuesList(abstract.List):
    
    def __init__(self, widget, core):
        self.core = core
        self.data_model = commands.DHValues(core)
        abstract.List.__init__(self, "gui:tailoring:values_list", core, widget)
        self.get_TreeView().set_enable_tree_lines(True)

        selection = self.get_TreeView().get_selection()
        selection.set_mode(gtk.SELECTION_SINGLE)

        # actions
        self.add_receiver("gui:tailoring:item_list", "update", self.__update)
        selection.connect("changed", self.__cb_item_changed, self.get_TreeView())

    def __update(self):
        self.data_model.fill()

    def __cb_item_changed(self, widget, treeView):

        selection = treeView.get_selection( )
        if selection != None: 
            (model, iter) = selection.get_selected( )
            if iter: self.core.selected_deps = model.get_value(iter, 0)


class ItemDetails(EventObject):

    def __init__(self, core):
        
        #create view
        self.core = core
        EventObject.__init__(self, self.core)
        self.data_model = commands.DataHandler(self.core)

        self.add_receiver("gui:tailoring:item_list", "update", self.__update)
        self.add_receiver("gui:tailoring:item_list", "changed", self.__update)
        self.draw()

    def __update(self):
        details = self.data_model.get_item_details(self.core.selected_item)
        self.id.set_text(details["id"])
        self.type.set_text(details["typetext"])
        self.weight.set_text(str(details["weight"]))
        if "idents" in details: 
            self.idents.set_text(str("\n".join([ident[0] for ident in details["idents"]])))

        # clear
        self.description.get_buffer().set_text("")
        self.fixes.get_buffer().set_text("")
        self.title.set_text("")
        for child in self.refBox.get_children():
            child.destroy()
        fixes = []

        if self.core.selected_lang in details["titles"]: 
            self.title.set_text(details["titles"][self.core.selected_lang])
        else: 
            for lang in details["titles"]:
                self.title.set_text(details["titles"][lang])
                break

        description = ""
        if self.core.selected_lang in details["descriptions"]: 
            description = details["descriptions"][self.core.selected_lang].replace("xhtml:","")
            description = description.replace("xmlns:", "")
        else: 
            for lang in details["descriptions"]:
                description = details["descriptions"][lang].replace("xhtml:","")
                break
        if description == "": description = "No description"
        description = "<body>"+description+"</body>"
        try:
            self.description.display_html(description)
        except Exception as err:
            logger.error("Exception: %s", err)
        
        for i, ref in enumerate(details["references"]):
            hbox = gtk.HBox()
            counter = gtk.Label("%d) " % (i+1,))
            counter.set_alignment(0,0)
            hbox.pack_start(counter, False, False)
            text = "<a href='%s'>%s</a>" % (ref["identifier"], " ".join((ref["title"] or "").split()))
            label = gtk.Label(text)
            hbox.pack_start(label, True, True)
            label.set_tooltip_text(ref["title"])
            label.set_use_markup(True)
	    try:
                label.set_track_visited_links(True)
	    except AttributeError: pass
            label.set_line_wrap(True)
            label.set_line_wrap_mode(pango.WRAP_WORD) 
            label.set_alignment(0,0)
            label.connect("size-allocate", render.label_size_allocate)
            hbox.show_all()
            self.refBox.pack_start(hbox, True, True)

        if "fixtexts" in details: fixes.extend(details["fixtexts"])
        if "fixes" in details: fixes.extend(details["fixes"])
        text = None
        for i, fixtext in enumerate(fixes):
            if text == None: text = ""
            hbox = gtk.HBox()
            text += "    "+fixtext["text"].replace("xhtml:", "").replace("xmlns:", "")+"<br>"
        if text == None: text = "No fixes specified"
        text = "<body>"+text+"</body>"
        try:
            self.fixes.display_html(text)
        except Exception as err:
            logger.warning("Exception: %s: (%s)", err, text)

    def draw(self):
        self.box_details = gtk.VBox()

        #info (id, title, type)
        expander = gtk.Expander("<b>Info</b>")
        expander.set_expanded(True)
        label = expander.get_label_widget()
        label.set_use_markup(True)
        alig = gtk.Alignment(0.5, 0.5, 1, 1)
        alig.set_padding(0, 10, 12, 4)
        expander.add(alig)
        vbox = gtk.VBox()
        alig.add(vbox)
        vbox.pack_start(gtk.HSeparator(), expand=False, fill=True, padding=1)
        self.box_details.pack_start(expander, expand=False, fill=True, padding=1)

        #id
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("ID: "), expand=False, fill=True, padding=1)
        self.id = gtk.Label("")
        self.id.set_alignment(0,0)
        hbox.pack_start(self.id, expand=True, fill=True, padding=1)
        vbox.pack_start(hbox, expand=False, fill=False, padding=1)

        #title
        hbox = gtk.HBox()
        label = gtk.Label("Title: ")
        label.set_alignment(0,0)
        hbox.pack_start(label, expand=False, fill=True, padding=1)
        self.title = gtk.Label("")
        self.title.set_line_wrap(True)
        self.title.set_line_wrap_mode(pango.WRAP_WORD)
        render.label_set_autowrap(self.title)
        self.title.set_alignment(0,0)
        hbox.pack_start(self.title, expand=True, fill=True, padding=1)
        vbox.pack_start(hbox, expand=False, fill=False, padding=1)

        #type
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("Type: "), expand=False, fill=True, padding=1)
        self.type = gtk.Label("")
        self.type.set_alignment(0,0)
        hbox.pack_start(self.type, expand=True, fill=True, padding=1)
        vbox.pack_start(hbox, expand=False, fill=False, padding=1)
        
        #weight
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("Weight: "), expand=False, fill=True, padding=1)
        self.weight = gtk.Label("")
        self.weight.set_alignment(0,0)
        hbox.pack_start(self.weight, expand=True, fill=True, padding=1)
        vbox.pack_start(hbox, expand=False, fill=False, padding=1)

        #CCE
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("Idents: "), expand=False, fill=False, padding=1)
        self.idents = gtk.Label("")
        self.idents.set_alignment(0,0)
        hbox.pack_start(self.idents, expand=True, fill=True, padding=1)
        vbox.pack_start(hbox, expand=False, fill=False, padding=1)
        
        #References
        expander = gtk.Expander("<b>References</b>")
        expander.set_expanded(False)
        label = expander.get_label_widget()
        label.set_use_markup(True)
        alig = gtk.Alignment(0.5, 0.5, 1, 1)
        alig.set_padding(0, 10, 12, 4)
        expander.add(alig)
        vbox = gtk.VBox()
        alig.add(vbox)
        vbox.pack_start(gtk.HSeparator(), expand=False, fill=True, padding=3)
        self.refBox = gtk.VBox()
        vbox.pack_start(self.refBox, expand=False, fill=False, padding=0)
        self.box_details.pack_start(expander, expand=False, fill=False, padding=1)
        
        # Get the background color from window and destroy it
        window = gtk.Window()
        nb = gtk.Notebook()
        window.add(nb)
        window.realize()
        nb.realize()
        bg_color = nb.get_style().bg[gtk.STATE_NORMAL]
        window.destroy()

        #fixes
        expander = gtk.Expander("<b>Fixes</b>")
        expander.set_expanded(False)
        label = expander.get_label_widget()
        label.set_use_markup(True)
        alig = gtk.Alignment(0, 0, 1, 1)
        alig.set_padding(0, 10, 12, 4)
        vbox = gtk.VBox()
        alig.add(vbox)
        vbox.pack_start(gtk.HSeparator(), expand=False, fill=False, padding=3)
        self.fixes = HtmlTextView()
        self.fixes.set_wrap_mode(gtk.WRAP_WORD)
        self.fixes.modify_base(gtk.STATE_NORMAL, bg_color)
        sw = gtk.ScrolledWindow()
        sw.set_property("hscrollbar-policy", gtk.POLICY_AUTOMATIC)
        sw.set_property("vscrollbar-policy", gtk.POLICY_AUTOMATIC)
        sw.set_property("border-width", 0)
        sw.add(self.fixes)
        sw.show()
        expander.add(alig)
        vbox.pack_start(sw, expand=False, fill=False, padding=1)
        self.box_details.pack_start(expander, expand=False, fill=False, padding=1)

        #description
        expander = gtk.Expander("<b>Description</b>")
        expander.set_expanded(True)
        label = expander.get_label_widget()
        label.set_use_markup(True)
        alig = gtk.Alignment(0, 0, 1, 1)
        alig.set_padding(0, 10, 12, 4)
        vbox = gtk.VBox()
        alig.add(vbox)
        vbox.pack_start(gtk.HSeparator(), expand=False, fill=False, padding=3)
        self.description = HtmlTextView()
        self.description.set_wrap_mode(gtk.WRAP_WORD)
        self.description.modify_base(gtk.STATE_NORMAL, bg_color)
        sw = gtk.ScrolledWindow()
        sw.set_property("hscrollbar-policy", gtk.POLICY_AUTOMATIC)
        sw.set_property("vscrollbar-policy", gtk.POLICY_AUTOMATIC)
        sw.set_property("border-width", 0)
        sw.add(self.description)
        sw.show()
        expander.add(alig)
        vbox.pack_start(sw, expand=True, fill=True, padding=1)
        self.box_details.pack_start(expander, expand=True, fill=True, padding=1)

class RefineDetails(EventObject):
    
    def __init__(self, builder, core):
        #create view
        self.builder = builder
        self.core = core
        EventObject.__init__(self, self.core)
        self.data_model = commands.DHProfiles(self.core)
        self.func = abstract.Func()
        self.add_receiver("gui:tailoring:item_list", "update", self.__update)
        self.add_receiver("gui:tailoring:item_list", "changed", self.__update)

        self.draw()

    def __update(self):

        details = self.data_model.get_item_details(self.core.selected_item)
        if details == None: return

        self.combo_role.handler_block_by_func(self.__cb_edit)
        self.combo_severity.handler_block_by_func(self.__cb_edit)
        if details["typetext"] == "Rule":

            self.combo_role.set_model(self.model_role)
            if "role" in details:
                self.func.set_active_comboBox(self.combo_role, details["role"] or 1, 0)
            else:
                self.combo_role.set_active(0)

            self.combo_severity.set_model(self.model_severity)
            if "severity" in details:
                self.func.set_active_comboBox(self.combo_severity, details["severity"] or 1, 0)
            else:
                self.combo_severity.set_active(0)
            
            self.entry_weight.set_sensitive(True)
            if "weight" in details:
                self.entry_weight.set_text(str(details["weight"]))
            else:
                self.entry_weight.set_text("")
            
        else:
            self.combo_role.set_model(gtk.ListStore(str))
            self.combo_severity.set_model(gtk.ListStore(str))
            self.entry_weight.set_text("")
            self.entry_weight.set_sensitive(False)

        self.combo_role.handler_unblock_by_func(self.__cb_edit)
        self.combo_severity.handler_unblock_by_func(self.__cb_edit)
            
    def draw(self):
        
        self.vbox_refines = gtk.VBox()
        alig = gtk.Alignment(0, 0)
        alig.set_padding(10, 10, 10, 10)
        self.vbox_refines.pack_start(alig, True, True)
        vbox_refines = gtk.VBox()
        alig.add(vbox_refines)
        
        self.model_role = abstract.Enum_type.combo_model_role
        self.combo_role = self.add_widget(vbox_refines, "<b>Role</b>", False, gtk.ComboBox())
        self.func.set_model_to_comboBox(self.combo_role, self.model_role, 1)
        self.combo_role.connect('changed', self.__cb_edit)
        
        self.model_severity = abstract.Enum_type.combo_model_level
        self.combo_severity = self.add_widget(vbox_refines, "<b>Severity</b>", False, gtk.ComboBox())
        self.func.set_model_to_comboBox(self.combo_severity, self.model_severity, 1)
        self.combo_severity.connect('changed', self.__cb_edit)
        
        self.entry_weight = self.add_widget(vbox_refines, "<b>Weight</b>", False, gtk.Entry())
        self.entry_weight.connect("focus-out-event", self.__cb_edit)
        
    def add_widget(self, body, text, expand, widget):
                
        frame = gtk.Frame(text)
        label = frame.get_label_widget()
        label.set_use_markup(True)        
        frame.set_shadow_type(gtk.SHADOW_NONE)
        if expand: body.pack_start(frame, True, True)
        else: body.pack_start(frame, False, True)
        alig = gtk.Alignment(0.5, 0.5, 1, 1)
        alig.set_padding(0, 0, 12, 0)
        frame.add(alig)
        alig.add(widget)
        return widget
        
    def __cb_edit(self, widget, event=None):
        weight = self.__cb_get_weight()
        self.data_model.change_refines( severity= abstract.Enum_type.combo_model_level[self.combo_severity.get_active()][0],
                                        role=abstract.Enum_type.combo_model_role[self.combo_role.get_active()][0],
                                        weight=weight)
        #raise NotImplementedError("Changing refines of \"%s\" not implemented." % (data,))
    
    def __cb_get_weight(self):
        weight = self.func.controlFloat(self.entry_weight.get_text(), "Weight", self.core.main_window)
        if weight:
            return weight
        else: 
            details = self.data_model.get_item_details(self.core.selected_item)
            if details == None: return

            if "weight" in details:
                return str(details["weight"])
            else: return None
        
class MenuButtonTailoring(abstract.MenuButton):
    """
    GUI for refines.
    """
    def __init__(self, builder, widget, core):
        abstract.MenuButton.__init__(self, "gui:btn:menu:tailoring", widget, core)
        self.builder = builder
        self.core = core

        # Profiles combo box
        self.profiles = self.builder.get_object("tailoring:profile")
        self.profile_model = commands.DHProfiles(core)
        self.profile_model.model = self.profiles.get_model()
        self.profile_model.fill()
        self.profiles.set_active(0)
        self.profiles.connect("changed", self.__cb_profile_changed, self.profiles.get_model())

        self.add_receiver("gui:btn:main:xccdf", "load", self.__profiles_update)
        self.add_receiver("gui:edit:profile_list", "update_profiles", self.__profiles_update)
        self.add_receiver("gui:btn:menu:edit:profiles", "update", self.__profiles_update)

        #draw body
        self.body = self.builder.get_object("tailoring:box")
        self.draw_nb(self.builder.get_object("tailoring:box_nb"))
        self.progress = self.builder.get_object("tailoring:progress")
        self.progress.hide()
        self.filter = filter.ItemFilter(self.core, self.builder, "tailoring:box_filter", "gui:btn:tailoring:filter")
        self.rules_list = ItemList(self.builder.get_object("tailoring:tw_items"), self.core, self.progress, self.filter)
        self.values = ValuesList(self.builder.get_object("tailoring:tw_values"), self.core)
        self.filter.expander.cb_changed()

        # set signals
        self.add_sender(self.id, "update")

    def update(self):
        for i, profile in enumerate(self.profile_model.model):
            if self.core.selected_profile == profile[0]:
                self.profiles.set_active(i)

    def __profiles_update(self):

        # need update because of new file loaded
        if self.profile_model.fill():
            self.profiles.set_active(0)
            self.core.selected_profile = self.profile_model.model[self.profiles.get_active()][0]

    def __cb_profile_changed(self, widget, model):

        if self.profiles.get_active() != -1:
            self.core.selected_profile = model[self.profiles.get_active()][0]
            self.emit("update")

    # draw notebook
    def draw_nb(self, box):
        # notebook for details and refines
        notebook = gtk.Notebook()
        box.pack_start(notebook, True, True)
 
        #Details 
        box_details = ItemDetails(self.core)
        notebook.append_page(box_details.box_details, gtk.Label("Details"))

        #set refines
        redDetails = RefineDetails(self.builder, self.core)
        notebook.append_page(redDetails.vbox_refines, gtk.Label("Refines"))
        notebook.show_all()
