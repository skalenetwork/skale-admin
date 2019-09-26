import React from 'react'

import {FlexCol, FlexCont} from "./shared_components/Flex";
import CertificateIcon from "./shared_components/CertificateIcon";

export default class CertificatePreview extends React.Component {
  render() {
    return (
      <div className="sk-list-item padd-top-15 padd-bott-15">
        <FlexCont className="fl-center-h">
          <FlexCol>
            <CertificateIcon status={this.props.item.status}/>
          </FlexCol>
          <FlexCol className="padd-left-md fl-grow">
            <h5 className="no-tmarg fw-6"
                style={{marginBottom: '3px'}}> {this.props.item.name} </h5>
            <FlexCont>
              <FlexCol>
                <p
                  className="no-marg fs-2 g-4 fw-5 marg-ri-10"> Status: {this.props.item.status}
                </p>
              </FlexCol>
            </FlexCont>
          </FlexCol>
        </FlexCont>
      </div>
    );
  }
}
