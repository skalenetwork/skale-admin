import React from 'react'

export class AccordionPart extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      collapse: props.collapse ? props.collapse : false
    };
    this.toggle = this.toggle.bind(this);
  }

  toggle() {
    this.setState({ collapse: !this.state.collapse });
  }

  render() {

    let accordionHeader = React.cloneElement(this.props.children[0], { toggle: this.toggle, collapse: this.state.collapse });
    let accordionContent = React.cloneElement(this.props.children[1], { collapse: this.state.collapse });

    return (
      <div className={"" + (this.props.last ? '' : 'bord-bott padd-bott-md marg-bott-md')} >
        {accordionHeader}
        {accordionContent}
      </div>
    );
  }
}
