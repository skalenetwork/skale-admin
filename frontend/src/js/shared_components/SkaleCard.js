import React from 'react'
export default class SkaleCard extends React.Component {
  render() {
    return (
      <div className={`skale-card padd-30 marg-bott-30 ${this.props.className}`}>
        {this.props.children}
      </div>
    );
  }
}
