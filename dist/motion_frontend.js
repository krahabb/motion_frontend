/* eslint-disable @typescript-eslint/no-explicit-any */
import {
    LitElement,
    html,
    customElement,
    property,
    CSSResult,
    TemplateResult,
    css,
    PropertyValues,
    internalProperty,
  } from 'lit-element';
  import {
    HomeAssistant,
    hasConfigOrEntityChanged,
    hasAction,
    ActionHandlerEvent,
    handleAction,
    //LovelaceCardEditor,
    getLovelace,
    ActionConfig, LovelaceCard, LovelaceCardConfig, LovelaceCardEditor
  } from 'custom-card-helpers'; // This is a community maintained npm module with common helper functions/types


export const CARD_VERSION = '0.0.1';
// TODO Add your configuration elements here for type-checking
/*
export interface BoilerplateCardConfig extends LovelaceCardConfig {
  type: string;
  name?: string;
  show_warning?: boolean;
  show_error?: boolean;
  test_gui?: boolean;
  entity?: string;
  tap_action?: ActionConfig;
  hold_action?: ActionConfig;
  double_tap_action?: ActionConfig;
}*/

function localize(msg, search = '', replace = '') {
    return msg
}

class MotionFrontendCameraCard extends LitElement {

    /*static async getConfigElement() {
      return document.createElement('motion-frontend-camera-card-editor');
    }

    static getStubConfig() {
      return {};
    }*/

    static get properties() {
        return {
          hass: {},
          config: {}
        };
      }


    setConfig(config) {
      if (!config) {
        throw new Error(localize('common.invalid_configuration'));
      }

      if (config.test_gui) {
        getLovelace().setEditMode(true);
      }

      this.config = {
        name: 'Motion Frontend Camera Name',
        ...config,
      };
    }


    render() {
      // TODO Check for stateObj or other necessary things and render a warning if missing
      if (this.config.show_warning) {
        return this._showWarning(localize('common.show_warning'));
      }

      if (this.config.show_error) {
        return this._showError(localize('common.show_error'));
      }

      return html`
        <ha-card
          .header=${this.config.name}
          @action=${this._handleAction}
          .actionHandler=${actionHandler({
            hasHold: hasAction(this.config.hold_action),
            hasDoubleClick: hasAction(this.config.double_tap_action),
          })}
          tabindex="0"
          .label=${`Boilerplate: ${this.config.entity || 'No Entity Defined'}`}
        ></ha-card>
      `;
    }

    _handleAction(ev) {
      if (this.hass && this.config && ev.detail.action) {
        handleAction(this, this.hass, this.config, ev.detail.action);
      }
    }

    _showWarning(warning) {
      return html`
        <hui-warning>${warning}</hui-warning>
      `;
    }

    _showError(error) {
      const errorCard = document.createElement('hui-error-card');
      errorCard.setConfig({
        type: 'error',
        error,
        origConfig: this.config,
      });

      return html`
        ${errorCard}
      `;
    }

}


// This puts your card into the UI card picker dialog
window.customCards = window.customCards || [];
window.customCards.push({
  type: "motion-frontend-camera-card",
  name: "Motion Frontend Camera Card",
  preview: false, // Optional - defaults to false
  description: "A custom card made by me!" // Optional
});
