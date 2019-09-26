import React from 'react'
import CardTitle from "../CardTitle";

import { Ripple } from 'rmwc/Ripple';
import {Icon} from 'rmwc/Icon';


export class AccordionHeader extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      collapse: false
    };
  }
  render() {
    return (
      <div className="fl-cont clickable" onClick={this.props.toggle}>
        <div className="fl-col fl-grow">
          <CardTitle icon={this.props.icon} text={this.props.text}/>
        </div>
        <div className="fl-col">
          <Ripple primary>
            <div className="accordion-h-icon">
              <Icon strategy="ligature" className="sm-icon gx-text-col">{this.props.collapse ? 'keyboard_arrow_up' : 'keyboard_arrow_down' } </Icon>
            </div>
          </Ripple>
        </div>

      </div>
    );
  }
}
