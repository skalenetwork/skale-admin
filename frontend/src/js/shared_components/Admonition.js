import React from 'react'
import {Icon} from 'rmwc/Icon';

export default class Admonition extends React.Component {

  getIcon() {
    switch (this.props.type) {
      case 'warning':
        return 'warning';
      default:
        return 'info';
    }
  }

  render() {
    return (
      <div className={`admonition ${this.props.className} ${this.props.type}`}>
        <div className={`fl-cont fl-center-vert admonition-title ${this.props.type}-bg`}>
          <div className='fl-col padd-ri-10' style={{height: "20px"}}>
            <Icon strategy="ligature" className="sm-icon">{this.getIcon()}</Icon>
          </div>
          <div className='fl-col'>
            <span className='g-6 fw-6'>{this.props.title}</span>
          </div>
        </div>
        <div className='padd-15'>
          {this.props.text}
        </div>
      </div>
    );
  }
}
