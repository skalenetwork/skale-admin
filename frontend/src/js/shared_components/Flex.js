import React from 'react'

export class FlexCont extends React.Component {
  render() {
    return (
      <div className={"fl-cont" + ' ' + (this.props.centered ? 'fl-center' : '') + ' ' + (this.props.className ? this.props.className : '')} >
        {this.props.children}
      </div>
    );
  }
}

export class FlexCol extends React.Component {
  render() {
    return (
      <div className={"fl-col"  + ' ' + (this.props.className ? this.props.className : '')}>
        {this.props.children}
      </div>
    );
  }
}
