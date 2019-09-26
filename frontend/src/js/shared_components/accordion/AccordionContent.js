import React from 'react'
import { Collapse } from 'reactstrap';

export class AccordionContent extends React.Component {

  render() {
    return (
      <div className="">
        <Collapse isOpen={this.props.collapse}>
          {this.props.children}
        </Collapse>
      </div>
    );
  }
}
