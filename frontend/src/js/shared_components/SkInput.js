import React from 'react'
import {Icon} from 'rmwc/Icon';
import {Input, Container, Tooltip} from 'reactstrap';
import SkaleButton from "../SkaleButton/SkaleButton";


export default class SkInput extends React.Component {

  getInputClass() {
    switch (this.props.valid) {
      case true:
        return 'valid';
      case false:
        return 'not-valid';
      case undefined:
        return ''
    }
  }

  render() {
    return (
      <div className={this.props.className}>
        <div className='fl-cont'>
          <div className='fl-col fl-grow'>
            <h6 className="fs-2 g-4 fw-4">{this.props.title}</h6>
          </div>
          <div className='fl-col'>
            <h6 className="fs-2 error-text fw-4">{this.props.error}</h6>
          </div>
        </div>

        <div className="fl-col fl-grow">
          <Input className={"new-input " + this.getInputClass()}
                 type={this.props.type}
                 disabled={this.props.disabled}
                 placeholder={this.props.placeholder}
                 onBlur={(num) =>
                   this.props.onBlur(num.target.value)}
                 onChange={(num) =>
                   this.props.updateVariable(num.target.value)}
                 value={this.props.value}
          />
        </div>
      </div>
    );
  }
}

SkInput.defaultProps = {
  type: 'text'
};