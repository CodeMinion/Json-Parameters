"""This file acts as the main module for this script."""

import traceback
import adsk.core
import adsk.fusion
# import adsk.cam
import json
import os 

# Initialize the global variables for the Application and UserInterface objects.
app = adsk.core.Application.get()
ui  = app.userInterface

handlers = []

palette_import_id = 'ParamImportPalette'
palette_export_id = 'ParamExportPalette'
temp_params = []  # Holds parsed JSON parameters
html_ready_flags = {
    'import': False,
    'export': False
}

def export_user_parameters():
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('No active Fusion 360 design', 'Error')
            return

        userParams = design.userParameters
        param_list = []

        for param in userParams:
            param_list.append({
                'name': param.name,
                'value': param.value,
                'expression': param.expression,
                'units': param.unit,
                'comment': param.comment
            })

        # Show file dialog
        fileDlg = ui.createFileDialog()
        fileDlg.title = "Save Parameters as JSON"
        fileDlg.filter = 'JSON files (*.json)'
        fileDlg.filterIndex = 0
        dialogResult = fileDlg.showSave()
        if dialogResult != adsk.core.DialogResults.DialogOK:
            return

        filePath = fileDlg.filename
        with open(filePath, 'w') as f:
            json.dump(param_list, f, indent=4)

        ui.messageBox(f'Exported {len(param_list)} user parameters to:\n{filePath}')
    except:
        ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

def show_import_palette(params_json):
    try:
        palette = ui.palettes.itemById(palette_import_id)
        if palette:
            palette.deleteMe()

        html_path = os.path.join(os.path.dirname(__file__), 'resources', 'param_ui.html')
        palette = ui.palettes.add(
            palette_import_id,
            'Import User Parameters',
            html_path,
            True, True, True, 400, 400
        )

        # Dock the palette to the right side of Fusion window.
        palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight

        on_close = PaletteClosedHandler()
        palette.closed.add(on_close)
        handlers.append(on_close)

        on_incoming = ImportHTMLMessageHandler()
        palette.incomingFromHTML.add(on_incoming)
        handlers.append(on_incoming)

        global temp_params
        temp_params = params_json
        
        #html_ready = False
        html_ready_flags['import'] = False
        
        #json_str = json.dumps(params_json)
        #ui.messageBox(json_str)
        # Send data to HTML
        # retVal = palette.sendInfoToHTML('loadParams', json_str)
        #ui.messageBox(f"Value returned {retVal}")

    except:
        ui.messageBox('Failed to show import palette:\n{}'.format(traceback.format_exc()))



def import_user_parameters():
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('No active design.')
            return

        fileDlg = ui.createFileDialog()
        fileDlg.title = "Open JSON Parameters"
        fileDlg.filter = 'JSON files (*.json)'
        fileDlg.filterIndex = 0
        if fileDlg.showOpen() != adsk.core.DialogResults.DialogOK:
            return

        with open(fileDlg.filename, 'r') as f:
            params = json.load(f)

        show_import_palette(params)
        
    except:
        ui.messageBox('Import failed:\n{}'.format(traceback.format_exc()))


class ImportHTMLMessageHandler(adsk.core.HTMLEventHandler):
    def notify(self, args):
        try:

            #ui.messageBox(args.data)

            if 'action' not in args.data:
                return

            msg = json.loads(args.data)
            
            is_msg_dict = isinstance(json.loads(args.data), dict)

            if not is_msg_dict:
                # Hack: Work around to handle the fact that when the html sends the data json.loads does not parse it right away into a dict. 
                msg = json.loads(f"{msg}")

            #ui.messageBox(f"{msg} - {len(msg)}")

            
            if msg['action'] == 'htmlReady':
                html_ready_flags['import'] = True
                palette = ui.palettes.itemById(palette_import_id)
                if palette and palette.isVisible:
                    # Now it's safe to send the parameters
                    palette.sendInfoToHTML('loadParams', json.dumps(temp_params))


            if msg['action'] == 'import':
                selected_names = set(msg['selected'])
                design = adsk.fusion.Design.cast(app.activeProduct)
                userParams = design.userParameters
                existing = {p.name for p in userParams}
                added = 0

                lst_failed_parameters = []
                for p in temp_params:
                    if p['name'] not in selected_names:
                        continue
                    if p['name'] in existing:
                        continue
                    expr = p.get('expression', str(p.get('value', 1)))
                    
                    name = p['name']
                    units = p.get('units', '')
                    comment = p.get('comment', '')
                    try:
                        userParams.add(
                            name,
                            adsk.core.ValueInput.createByString(expr),
                            units,
                            comment
                        )
                        added += 1
                    except:
                        # Track paramter that fialed. 
                        failed_tuple = (name, expr, units, comment)
                        lst_failed_parameters.append(failed_tuple)
                        pass    

                for failed_tuple in lst_failed_parameters:
                    name, expr, units, comment = failed_tuple
                    userParams.add(
                            name,
                            adsk.core.ValueInput.createByString(expr),
                            units,
                            comment
                        )
                    added += 1

                ui.messageBox(f'Imported {added} parameters.')
                palette = ui.palettes.itemById(palette_import_id)
                if palette:
                    palette.isVisible = False

        except:
            ui.messageBox('Import HTML Message Error:\n{}'.format(traceback.format_exc()))

class ExportHTMLMessageHandler(adsk.core.HTMLEventHandler):
    def notify(self, args):

        #ui.messageBox(args.data)

        if 'action' not in args.data:
            return

        msg = json.loads(args.data)
            
        is_msg_dict = isinstance(json.loads(args.data), dict)

        if not is_msg_dict:
            # Hack: Work around to handle the fact that when the html sends the data json.loads does not parse it right away into a dict. 
            msg = json.loads(f"{msg}")

        if msg['action'] == 'htmlReady':
            html_ready_flags['export'] = True
            palette = ui.palettes.itemById(palette_export_id)
            if palette and palette.isVisible:
                palette.sendInfoToHTML('loadExportParams', json.dumps(temp_params))


        elif msg['action'] == 'export':
            selected_names = set(msg['selected'])
            export_data = [p for p in temp_params if p['name'] in selected_names]

            # Ask user where to save
            fileDlg = ui.createFileDialog()
            fileDlg.title = "Save Exported Parameters"
            fileDlg.filter = 'JSON files (*.json)'
            if fileDlg.showSave() != adsk.core.DialogResults.DialogOK:
                return
            with open(fileDlg.filename, 'w') as f:
                json.dump(export_data, f, indent=4)

            ui.messageBox(f'Exported {len(export_data)} parameters.')
            palette = ui.palettes.itemById(palette_export_id)
            if palette:
                palette.isVisible = False
        pass
    pass

class PaletteClosedHandler(adsk.core.UserInterfaceGeneralEventHandler):
    def notify(self, args):
        try:
            #ui.messageBox('Parameter import canceled.')
            # Do nothing.
            pass
        except:
            pass


# Export CommandCreated event handler
class ExportParamsCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            onExecute = ExportParamsCommandExecuteHandler()
            cmd.execute.add(onExecute)
            handlers.append(onExecute)
        except:
            ui.messageBox('ExportCommandCreated Failed:\n{}'.format(traceback.format_exc()))

# Export Command execution
class ExportParamsCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        #export_user_parameters()
        try:  
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                ui.messageBox('No active design.')
                return

            userParams = design.userParameters
            global temp_params, html_ready_flags
            temp_params = [{
                'name': p.name,
                'value': p.value,
                'expression': p.expression,
                'units': p.unit,
                'comment': p.comment
            } for p in userParams]

            html_ready_flags['export'] = False
            palette = ui.palettes.itemById(palette_export_id)
            if palette:
                palette.deleteMe()

            
            html_path = os.path.join(os.path.dirname(__file__), 'resources', 'param_ui.html')
            palette = ui.palettes.add(
                palette_export_id,
                'Export Parameters',
                html_path,
                True, True, True, 400, 400
            )

            # Dock the palette to the right side of Fusion window.
            palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight

            on_close = PaletteClosedHandler()
            palette.closed.add(on_close)
            handlers.append(on_close)

            on_incoming = ExportHTMLMessageHandler()
            palette.incomingFromHTML.add(on_incoming)
            handlers.append(on_incoming)

        except:
            ui.messageBox('Export command failed:\n{}'.format(traceback.format_exc()))
        pass

class ImportParamsCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            onExecute = ImportParamsCommandExecuteHandler()
            cmd.execute.add(onExecute)
            handlers.append(onExecute)
        except:
            ui.messageBox('ImportCommandCreated Failed:\n{}'.format(traceback.format_exc()))

class ImportParamsCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, eventArgs):
        import_user_parameters()
    

def run(_context: str):
    """This function is called by Fusion when the script is run."""

    try:
        exportCmdId = 'ExportUserParams'
        exportCmdDef = ui.commandDefinitions.itemById(exportCmdId)
        if not exportCmdDef:
            exportCmdDef = ui.commandDefinitions.addButtonDefinition(
                exportCmdId,
                'Export User Parameters',
                'Exports user parameters to a JSON file.',
                ''  # Resource folder
            )
            #ui.messageBox("Added export command")

        onCommandCreated = ExportParamsCommandCreatedHandler()
        exportCmdDef.commandCreated.add(onCommandCreated)
        handlers.append(onCommandCreated)

        # Add to UI
        solidPanel = ui.allToolbarPanels.itemById('SolidModifyPanel')
        exportControl = solidPanel.controls.itemById(exportCmdId)

        referenceControl = solidPanel.controls.itemById('FusionChangeParametersCmd')
        insertIndex = referenceControl.index + 1 if referenceControl else -1
        
        if not exportControl:
            exportControl = solidPanel.controls.addCommand(exportCmdDef)
            if insertIndex > 0:
                solidPanel.controls.move(exportControl.index, insertIndex)
            #ui.messageBox("Added control") 

        else:
            ui.messageBox("Unable to add export control")    

        # Add import command
        importCmdId = 'ImportUserParams'
        importCmdDef = ui.commandDefinitions.itemById(importCmdId)
        if not importCmdDef:
            # Add the command 
            importCmdDef =  ui.commandDefinitions.addButtonDefinition(
                importCmdId,
                'Import User Parameters',
                'Imports user parameters from a JSON file.',
                ''  # Resource folder
            )

        onImportCommandCreated = ImportParamsCommandCreatedHandler()
        importCmdDef.commandCreated.add(onImportCommandCreated)
        handlers.append(onImportCommandCreated)

        importControl = solidPanel.controls.itemById(importCmdId)
        if not importControl:
            # Add import control
            importControl = solidPanel.controls.addCommand(importCmdDef)
            if insertIndex > 0:
                solidPanel.controls.move(importControl.index, insertIndex + 1)
       
        #ui.messageBox(f'"{app.activeDocument.name}" is the active Document.')

    except:
        ui.messageBox('Add-in failed:\n{}'.format(traceback.format_exc()))


def stop(context):
    try:
        for cmdId in ['ExportUserParams', 'ImportUserParams']:
            cmdDef = ui.commandDefinitions.itemById(cmdId)
            if cmdDef: cmdDef.deleteMe()

            panel = ui.allToolbarPanels.itemById('SolidModifyPanel')
            ctrl = panel.controls.itemById(cmdId)
            if ctrl: ctrl.deleteMe()
    except:
        ui.messageBox('Stop failed:\n{}'.format(traceback.format_exc()))

'''
import adsk.core, traceback
import codecs

def run(context):
    ui = None
    try:
        app: adsk.core.Application = adsk.core.Application.get()
        ui  = app.userInterface

        fileDialog = ui.createFileDialog()
        fileDialog.isMultiSelectEnabled = False
        fileDialog.title = "Specify result filename"
        fileDialog.filter = 'XML files (*.xml)'
        fileDialog.filterIndex = 0
        dialogResult = fileDialog.showSave()
        if dialogResult == adsk.core.DialogResults.DialogOK:
            filename = fileDialog.filename
        else:
            return

        result = '<UserInterface>\n'
        result += f'{TabSpace(1)}<Workspaces count="{ui.workspaces.count}">\n'
        for wsIndex in range(ui.workspaces.count):
            try:
                ws: adsk.core.Workspace = ui.workspaces.item(wsIndex)
            except:
                ws = None

            if ws:
                result += f'{TabSpace(2)}<Workspace name="{ws.name}" id="{ws.id}">\n'
                try:
                    tabs = ws.toolbarTabs
                except:
                    tabs = None

                if tabs:
                    result += f'{TabSpace(3)}<ToolbarTabs count="{tabs.count}">\n'
                    for tab in tabs:
                        result += f'{TabSpace(4)}<ToolbarTab name="{tab.name}" id="{tab.id}">\n'

                        result += GetPanelsXML(tab.toolbarPanels, 5)

                        result += f'{TabSpace(4)}</ToolbarTab>\n'

                    result += f'{TabSpace(3)}</ToolbarTabs>\n'
                else:
                    result += f'{TabSpace(3)}<ToolbarTabs error="Failed to get toolbar tabs.">\n'
                    result += f'{TabSpace(3)}</ToolbarTabs>\n'

                result += f'{TabSpace(2)}</Workspace>\n'

        result += f'{TabSpace(1)}</Workspaces>\n'

        result += f'{TabSpace(1)}<Toolbars count="{ui.toolbars.count}">\n'
        toolbar: adsk.core.Toolbar
        for toolbar in ui.toolbars:
            result += f'{TabSpace(2)}<Toolbar id="{toolbar.id}">\n'
            result += f'{TabSpace(3)}<ToolbarControls count="{toolbar.controls.count}">\n'
            result += GetControls(toolbar.controls, 1, False)
            result += f'{TabSpace(3)}</ToolbarControls>\n'
            result += f'{TabSpace(2)}</Toolbar>\n'
        result += f'{TabSpace(1)}</Toolbars>\n'
        result += '</UserInterface>'

        f = open(filename, 'w', -1, 'utf-8-sig')
        f.write(result)
        f.close()
        ui.messageBox(f'Finished writing to:\n{filename}')
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


# Builds XML data for all of the panel information from the ToolbarPanels collection passed in.
def GetPanelsXML(panels: adsk.core.ToolbarPanels, tabs: int) -> str:
    result = f'{TabSpace(tabs)}<ToolbarPanels count="{panels.count}">\n'
    for panelIndex in range(panels.count):
        try:
            panel: adsk.core.ToolbarPanel = panels.item(panelIndex)
        except:
            panel = None

        if panel:
            result += f'{TabSpace(tabs + 1)}<ToolbarPanel name="{panel.name}" id="{panel.id}">\n'
            result += f'{TabSpace(tabs + 2)}<ToolbarControls count="{panel.controls.count}">\n'
            result += GetControls(panel.controls, tabs, True)
            result += f'{TabSpace(tabs + 2)}</ToolbarControls>\n'
            result += f'{TabSpace(tabs + 1)}</ToolbarPanel>\n'

    result += f'{TabSpace(tabs + 1)}</ToolbarPanels>\n'
    return result


# Builds XML data for all of the controls in the ToolbarControls collection passed in.
def GetControls(controls: adsk.core.ToolbarControls, tabs: int, isPanel: bool) -> str:
    result = ''
    for control in controls:
        if control.objectType == adsk.core.DropDownControl.classType():
            dropControl: adsk.core.DropDownControl = control

            if isPanel:
                try:
                    dropName = dropControl.name
                except:
                    dropName = "**** Error getting name."

                result += f'{TabSpace(tabs + 3)}<DropDownControl name="{dropName}" id="{dropControl.id}" count="{dropControl.controls.count}">\n'
            else:
                result += f'{TabSpace(tabs + 3)}<DropDownControl id="{dropControl.id}" count="{dropControl.controls.count}">\n'

            result += GetControls(dropControl.controls, tabs + 1, isPanel)
            result += f'{TabSpace(tabs + 3)}</DropDownControl>\n'
        elif control.objectType == adsk.core.SplitButtonControl.classType():
            splitControl: adsk.core.SplitButtonControl = control
            result += f'{TabSpace(tabs + 3)}<SplitButtonControl>\n'

            try:
                defaultCmdDef = splitControl.defaultCommandDefinition
            except:
                defaultCmdDef = None
            
            if defaultCmdDef:
                result += f'{TabSpace(tabs + 4)}<defaultCommandDefinition name="{defaultCmdDef.name}" id="{defaultCmdDef.id}"/>\n'

                additionalDefs = splitControl.additionalDefinitions
                result += f'{TabSpace(tabs + 4)}<additionalDefinitions count="{len(additionalDefs)}">\n'
                for additionalDef in additionalDefs:
                    result += f'{TabSpace(tabs + 5)}<{ObjectName(additionalDef)} name="{additionalDef.name}" id="{additionalDef.id}"/>\n'
                result += f'{TabSpace(tabs + 4)}</additionalDefinitions>\n'
            else:
                result += f'{TabSpace(tabs + 4)}<defaultCommandDefinition error="**** Failed to get CommandDefinition"/>\n'

            result += f'{TabSpace(tabs + 3)}</SplitButtonControl>\n'

        else:
            if control.objectType == adsk.core.SeparatorControl.classType():
                result += f'{TabSpace(tabs + 3)}<SeparatorControl id="{control.id}" />\n'
            else:
                cmdDef: adsk.core.CommandDefinition = None
                try:                 
                    cmdDef = control.commandDefinition
                except:
                    cmdDef = None

                if cmdDef:
                    try:
                        commandType = ObjectName(cmdDef.controlDefinition)
                    except:
                        commandType = '**** Failed to get associated control.'

                    isPromotedOK = True
                    try:
                        isPromoted = control.isPromoted
                    except:
                        isPromotedOK = False


                    if isPanel and isPromotedOK:
                        result += f'{TabSpace(tabs + 3)}<{ObjectName(control)} name="{cmdDef.name}" id="{cmdDef.id}" commandType="{commandType}" isPromoted="{isPromoted}" />\n'
                    else:
                        result += f'{TabSpace(tabs + 3)}<{ObjectName(control)} name="{cmdDef.name}" id="{cmdDef.id}" commandType="{commandType}" />\n'
                else:
                    result += f'{TabSpace(tabs + 3)}<{ObjectName(control)} error="**** Failed to get CommandDefinition for {control.id}" />\n'

    return result


# Return a string of spaces that can be used to prepend to a string to
# represent the specified number of tabs. 
def TabSpace(tabs: int) -> str:
    spacesPerTab = 4
    return ' ' * (spacesPerTab * tabs)


# Splits out the object name from the full object name passed in.
def ObjectName(object: adsk.core.Base) -> str:
    parts = object.objectType.split('::')
    return parts[len(parts)-1]
'''
