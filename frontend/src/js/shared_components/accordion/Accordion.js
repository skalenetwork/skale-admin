import React from 'react'
import { AccordionHeader } from './AccordionHeader'
import { AccordionContent } from './AccordionContent'
import { AccordionPart } from './AccordionPart'

export { AccordionHeader } from './AccordionHeader'
export { AccordionContent } from './AccordionContent'
export { AccordionPart } from './AccordionPart'

export class Accordion extends React.Component {

  constructor(props){
    super(props);
  }

  render() {
    return (
      <div>
        {this.props.children}
      </div>
    );
  }
}
